import json
from io import BytesIO
from html import escape

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    SimpleDocTemplate,
)

from database.supabase_client import get_supabase


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AegisAI — Report",
    page_icon="🛡️",
    layout="wide",
)


# ============================================================
# AUTHENTICATION
# ============================================================

if "user" not in st.session_state:
    st.warning("Please log in to continue.")
    st.stop()

user = st.session_state["user"]


# ============================================================
# HELPERS
# ============================================================

def safe_text(value, default="N/A"):
    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return default

        return value

    return str(value)


def format_amount(value):
    try:
        return f"PKR {float(value):,.0f}"
    except Exception:
        return "PKR 0"


def format_timestamp(value):
    if not value:
        return "N/A"

    text = str(value)

    if "T" in text:
        text = text.replace("T", " ", 1)

    if "+" in text:
        text = text.split("+", 1)[0]

    if text.endswith("Z"):
        text = text[:-1]

    return text


def parse_json(value, default=None):
    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default

    return default


def get_case_id(case):
    try:
        return int(case.get("id"))
    except Exception:
        return case.get("id")


def normalize_result(value):
    """
    Convert an agent/review result into a dictionary when possible.
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        parsed = parse_json(value, {})

        if isinstance(parsed, dict):
            return parsed

    return {}


def result_text(result):
    """
    Convert an AI result into readable text for the UI/PDF.
    Handles the structured JSON produced by the agents as well as
    plain-text fallback content.
    """
    if result is None:
        return "No assessment available."

    if isinstance(result, str):
        text = result.strip()

        if not text:
            return "No assessment available."

        parsed = parse_json(text, None)

        if isinstance(parsed, dict):
            return result_text(parsed)

        return text

    if not isinstance(result, dict):
        return safe_text(result)

    preferred_keys = [
        "assessment",
        "summary",
        "executive_summary",
        "overall_assessment",
        "result",
        "analysis",
        "findings",
        "recommendation",
        "details",
        "text",
    ]

    sections = []

    for key in preferred_keys:
        value = result.get(key)

        if value is None:
            continue

        if isinstance(value, list):
            if value:
                sections.append(
                    f"{key.replace('_', ' ').title()}:"
                )

                for item in value:
                    sections.append(f"• {safe_text(item)}")

        elif isinstance(value, dict):
            sections.append(
                f"{key.replace('_', ' ').title()}:"
            )

            for sub_key, sub_value in value.items():
                sections.append(
                    f"{sub_key.replace('_', ' ').title()}: "
                    f"{safe_text(sub_value)}"
                )

        else:
            sections.append(
                f"{key.replace('_', ' ').title()}: "
                f"{safe_text(value)}"
            )

    if sections:
        return "\n".join(sections)

    # Generic dictionary fallback
    fallback = []

    for key, value in result.items():
        if value is None:
            continue

        if isinstance(value, list):
            fallback.append(
                f"{key.replace('_', ' ').title()}:"
            )

            for item in value:
                fallback.append(f"• {safe_text(item)}")

        elif isinstance(value, dict):
            fallback.append(
                f"{key.replace('_', ' ').title()}:"
            )

            for sub_key, sub_value in value.items():
                fallback.append(
                    f"{sub_key.replace('_', ' ').title()}: "
                    f"{safe_text(sub_value)}"
                )

        else:
            fallback.append(
                f"{key.replace('_', ' ').title()}: "
                f"{safe_text(value)}"
            )

    if fallback:
        return "\n".join(fallback)

    return "No assessment available."


def extract_assessment(review, field_name):
    """
    Retrieve a saved agent assessment from ai_reviews.

    AegisAI stores the agent results using:
        compliance
        financial
        risk

    The helper also supports the older *_result field names
    so the report remains compatible with previously stored
    review records.
    """
    if not review:
        return {}

    value = review.get(field_name)

    if value is None:
        legacy_field = f"{field_name}_result"
        value = review.get(legacy_field)

    if value is None:
        return {}

    return normalize_result(value)
    
def extract_synthesis(review):
    """
    Retrieve the Decision Synthesizer result.
    """
    if not review:
        return {}

    return normalize_result(
        review.get("synthesis")
    )


def get_nested_value(data, *keys):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

        if current is None:
            return None

    return current


def display_multiline_text(text):
    """
    Render newline-separated AI content cleanly in Streamlit.
    """
    if not text:
        st.write("No assessment available.")
        return

    for line in str(text).splitlines():
        line = line.strip()

        if not line:
            st.write("")
            continue

        if line.startswith("•"):
            st.markdown(line)
        elif line.startswith("-"):
            st.markdown(line)
        elif line[:2].isdigit() and line[2:3] == ".":
            st.markdown(line)
        else:
            st.write(line)


def pdf_escape(value):
    return escape(safe_text(value)).replace("\n", "<br/>")


def pdf_paragraph(text, style):
    return Paragraph(
        pdf_escape(text).replace("•", "&bull;"),
        style,
    )


def add_pdf_section_title(story, title, style):
    story.append(
        Paragraph(
            escape(title),
            style,
        )
    )
    story.append(Spacer(1, 3 * mm))


def add_pdf_text(story, text, style):
    if not text:
        return

    for line in str(text).splitlines():
        line = line.strip()

        if not line:
            story.append(Spacer(1, 2 * mm))
            continue

        story.append(
            Paragraph(
                pdf_escape(line).replace("•", "&bull;"),
                style,
            )
        )

        story.append(Spacer(1, 1.5 * mm))


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown("## 🛡️ AegisAI")
    st.caption("Approval & Compliance System")

    st.markdown("---")

    st.markdown("### Navigation")

    if st.button(
        "Dashboard",
        use_container_width=True,
    ):
        st.switch_page("pages/1_Dashboard.py")

    if st.button(
        "Create Approval Case",
        use_container_width=True,
    ):
        st.switch_page("pages/2_Create_Case.py")

    if st.button(
        "Case Review",
        use_container_width=True,
    ):
        st.switch_page("pages/3_Case_Review.py")

    if st.button(
        "Decision",
        use_container_width=True,
    ):
        st.switch_page("pages/4_Decision.py")

    if st.button(
        "Case History",
        use_container_width=True,
    ):
        st.switch_page("pages/5_Case_History.py")

    if st.button(
        "Reports",
        use_container_width=True,
        type="primary",
    ):
        st.rerun()

    st.markdown("---")

    if st.button(
        "Logout",
        use_container_width=True,
    ):
        st.session_state.pop("user", None)
        st.switch_page("app.py")


# ============================================================
# PAGE HEADER
# ============================================================

st.title("AegisAI — Approval & Compliance Report")

st.caption(
    "Generate a case-specific report containing AI analysis, "
    "policy evidence, human decision, workflow checkpoints, "
    "and audit history."
)


# ============================================================
# SUPABASE CONNECTION
# ============================================================

try:
    supabase = get_supabase()
except Exception as exc:
    st.error(f"Unable to connect to the database: {exc}")
    st.stop()


# ============================================================
# LOAD USER CASES
# ============================================================

try:
    cases_response = (
        supabase
        .table("cases")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )

    cases = cases_response.data or []

except Exception as exc:
    st.error(f"Unable to load approval cases: {exc}")
    st.stop()


if not cases:
    st.info("No approval cases are available.")
    st.stop()


# ============================================================
# CASE SELECTOR
# ============================================================

case_options = {}

for case_item in cases:
    title = case_item.get(
        "title",
        "Untitled",
    )

    amount_display = format_amount(
        case_item.get(
            "amount",
            0,
        )
    )

    case_id_value = case_item.get("id")

    label = (
        f"{title} — "
        f"{amount_display} — "
        f"Case #{case_id_value}"
    )

    case_options[label] = case_item


selected_label = st.selectbox(
    "Select Case",
    list(case_options.keys()),
)


case = case_options[selected_label]

case_id = get_case_id(case)


# ============================================================
# LOAD LATEST AI REVIEW FOR SELECTED CASE ONLY
# ============================================================

try:
    review_response = (
        supabase
        .table("ai_reviews")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    reviews = review_response.data or []

except Exception as exc:
    st.error(f"Unable to load AI review: {exc}")
    st.stop()


review = reviews[0] if reviews else None


# ============================================================
# LOAD WORKFLOW CHECKPOINTS FOR SELECTED CASE ONLY
# ============================================================

try:
    steps_response = (
        supabase
        .table("ai_review_steps")
        .select("*")
        .eq("case_id", case_id)
        .order("step_order")
        .execute()
    )

    steps = steps_response.data or []

except Exception as exc:
    st.error(
        f"Unable to load AI workflow checkpoints: {exc}"
    )
    st.stop()


# ============================================================
# LOAD HUMAN DECISION FOR SELECTED CASE ONLY
# ============================================================

try:
    decision_response = (
        supabase
        .table("decisions")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    decisions = decision_response.data or []

except Exception as exc:
    st.error(
        f"Unable to load human decision: {exc}"
    )
    st.stop()


decision = decisions[0] if decisions else None


# ============================================================
# LOAD AUDIT TRAIL FOR SELECTED CASE ONLY
# ============================================================

try:
    audit_response = (
        supabase
        .table("audit_logs")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
    )

    audit_logs = audit_response.data or []

except Exception as exc:
    st.error(
        f"Unable to load audit trail: {exc}"
    )
    st.stop()


# ============================================================
# EXTRACT AI DATA
# ============================================================

requirements = []

evidence_gate = {}

compliance_result = {}
financial_result = {}
risk_result = {}
synthesis_result = {}

if review:
    requirements = parse_json(
        review.get("requirements"),
        [],
    )

    if not isinstance(requirements, list):
        requirements = []

    evidence_gate = parse_json(
        review.get("evidence_gate"),
        {},
    )

    if not isinstance(evidence_gate, dict):
        evidence_gate = {}

    compliance_result = extract_assessment(
        review,
        "compliance",
    )

    financial_result = extract_assessment(
        review,
        "financial",
    )
    
    risk_result = extract_assessment(
        review,
        "risk",
    )


# ============================================================
# PAGE CASE INFORMATION
# ============================================================

st.markdown("---")
st.subheader("Case Information")

case_col1, case_col2, case_col3, case_col4 = st.columns(4)

with case_col1:
    st.metric(
        "Case ID",
        safe_text(case_id),
    )

with case_col2:
    st.metric(
        "Status",
        safe_text(
            case.get("status"),
            "DRAFT",
        ).upper(),
    )

with case_col3:
    st.metric(
        "Department",
        safe_text(
            case.get("department"),
        ),
    )

with case_col4:
    st.metric(
        "Amount",
        format_amount(
            case.get("amount", 0)
        ),
    )

st.write(
    f"**Case:** {safe_text(case.get('title'))}"
)

st.write(
    f"**Created:** "
    f"{format_timestamp(case.get('created_at'))}"
)


# ============================================================
# EVIDENCE GATE
# ============================================================

st.markdown("---")
st.subheader("Evidence Gate")

gate_complete = bool(
    evidence_gate.get("complete", False)
)

missing_requirements = evidence_gate.get(
    "missing",
    [],
)

if not isinstance(missing_requirements, list):
    missing_requirements = []

if gate_complete:
    st.success("Status: PASSED")
else:
    st.error("Status: INCOMPLETE")

if missing_requirements:
    st.markdown("### Missing Requirements")

    for item in missing_requirements:
        if isinstance(item, dict):
            st.write(
                f"• {safe_text(item.get('name'))}"
            )
        else:
            st.write(
                f"• {safe_text(item)}"
            )


# ============================================================
# POLICY-DRIVEN REQUIREMENTS
# ============================================================

st.markdown("---")
st.subheader("Policy-Driven Requirements")

if requirements:
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue

        name = safe_text(
            requirement.get("name"),
            "Requirement",
        )

        status = safe_text(
            requirement.get("status"),
            "UNKNOWN",
        ).upper()

        mandatory = (
            "Mandatory"
            if requirement.get("mandatory", False)
            else "Conditional"
        )

        reason = safe_text(
            requirement.get("reason")
        )

        evidence_rule = safe_text(
            requirement.get("evidence_rule")
        )

        minimum_count = requirement.get(
            "minimum_count"
        )

        minimum_text = ""

        if minimum_count:
            minimum_text = (
                f" — Minimum: {minimum_count}"
            )

        st.markdown(
            f"**{name}** — "
            f"{mandatory} — "
            f"{status}{minimum_text}"
        )

        st.caption(
            f"Reason: {reason}"
        )

        st.caption(
            f"Policy / Evidence Rule: "
            f"{evidence_rule}"
        )
else:
    st.info(
        "No policy-driven requirements were recorded."
    )


# ============================================================
# AI ASSESSMENT
# ============================================================

st.markdown("---")
st.subheader("AI Assessment")

if not review:
    st.warning(
        "No completed AI assessment is available "
        "for this case."
    )
else:
    synthesis_text = result_text(
        synthesis_result
    )

    st.markdown(
        f"**AI Recommendation:** "
        f"{safe_text(review.get('recommendation'))}"
    )

    st.markdown("### Executive Summary")

    executive_summary = (
        synthesis_result.get(
            "executive_summary"
        )
        or synthesis_result.get(
            "summary"
        )
    )

    if executive_summary:
        display_multiline_text(
            executive_summary
        )
    else:
        st.info(
            "No separate executive summary was recorded."
        )

    st.markdown("### Compliance Assessment")

    compliance_text = result_text(
        compliance_result
    )

    display_multiline_text(
        compliance_text
    )

    st.markdown("### Financial Assessment")

    financial_text = result_text(
        financial_result
    )

    display_multiline_text(
        financial_text
    )

    st.markdown("### Risk Assessment")

    risk_text = result_text(
        risk_result
    )

    display_multiline_text(
        risk_text
    )

    # --------------------------------------------------------
    # Extract selected synthesis sections only.
    # This avoids repeating the entire synthesis.
    # --------------------------------------------------------

    for section_key, section_title in [
        ("key_findings", "Key Findings"),
        (
            "missing_or_unclear_information",
            "Missing or Unclear Information",
        ),
        (
            "critical_policy_control_issues",
            "Critical Policy / Control Issues",
        ),
        (
            "critical_policy_issues",
            "Critical Policy / Control Issues",
        ),
        (
            "required_actions_before_final_decision",
            "Required Actions Before Final Decision",
        ),
        (
            "required_actions",
            "Required Actions",
        ),
    ]:
        section_value = synthesis_result.get(
            section_key
        )

        if section_value is None:
            continue

        st.markdown(
            f"### {section_title}"
        )

        if isinstance(section_value, list):
            for index, item in enumerate(
                section_value,
                start=1,
            ):
                st.write(
                    f"{index}. {safe_text(item)}"
                )
        else:
            display_multiline_text(
                section_value
            )

    human_review_required = (
        synthesis_result.get(
            "human_review_required"
        )
    )

    if human_review_required is None:
        human_review_required = (
            review.get("human_review_required")
            if review
            else None
        )

    if human_review_required is not None:
        st.markdown(
            f"**Human Review Required:** "
            f"{'YES' if human_review_required else 'NO'}"
        )


# ============================================================
# HUMAN DECISION
# ============================================================

st.markdown("---")
st.subheader("Human Decision")

if decision:
    decision_value = safe_text(
        decision.get("decision"),
        "N/A",
    )

    st.markdown(
        f"**Final Decision:** {decision_value.title()}"
    )

    st.write(
        f"**Decision Date:** "
        f"{format_timestamp(decision.get('created_at'))}"
    )

    comments = decision.get("comments")

    if comments:
        st.write(
            f"**Comments:** {safe_text(comments)}"
        )
else:
    st.info(
        "No human decision has been recorded "
        "for this case."
    )


# ============================================================
# AI WORKFLOW CHECKPOINTS
# ============================================================

st.markdown("---")
st.subheader("AI Workflow Checkpoints")

if steps:
    workflow_rows = []

    for step in steps:
        workflow_rows.append(
            [
                safe_text(
                    step.get("step_name")
                ),
                safe_text(
                    step.get("status")
                ).upper(),
                safe_text(
                    step.get("provider")
                ),
                safe_text(
                    step.get("model")
                ),
            ]
        )

    st.table(
        {
            "Step": [
                row[0]
                for row in workflow_rows
            ],
            "Status": [
                row[1]
                for row in workflow_rows
            ],
            "Provider": [
                row[2]
                for row in workflow_rows
            ],
            "Model": [
                row[3]
                for row in workflow_rows
            ],
        }
    )
else:
    st.info(
        "No AI workflow checkpoints were recorded."
    )


# ============================================================
# AUDIT TRAIL
# ============================================================

st.markdown("---")
st.subheader("Audit Trail")

if audit_logs:
    for log in audit_logs:
        timestamp = format_timestamp(
            log.get("created_at")
        )

        action = safe_text(
            log.get("action"),
            "AUDIT_EVENT",
        )

        description = safe_text(
            log.get("description"),
            "",
        )

        metadata = parse_json(
            log.get("metadata"),
            {},
        )

        line = (
            f"**{timestamp} — {action}**"
        )

        if description:
            line += f" — {description}"

        st.markdown(line)

        if metadata:
            st.caption(
                json.dumps(
                    metadata,
                    ensure_ascii=False,
                )
            )
else:
    st.info(
        "No audit events were recorded."
    )


# ============================================================
# PDF GENERATION
# ============================================================

def generate_pdf():
    """
    Generate a PDF using ONLY the currently selected case
    and records loaded using that case_id.

    No other case is queried or included.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=(
            f"AegisAI Case {case_id} "
            "Approval & Compliance Report"
        ),
        author="AegisAI",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AegisTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )

    section_style = ParagraphStyle(
        "AegisSection",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )

    subsection_style = ParagraphStyle(
        "AegisSubsection",
        parent=styles["Heading3"],
        fontSize=11,
        leading=14,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )

    body_style = ParagraphStyle(
        "AegisBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        spaceAfter=1.5 * mm,
    )

    small_style = ParagraphStyle(
        "AegisSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
    )

    story = []

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "AegisAI — Approval & Compliance Report",
            title_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Case #{escape(safe_text(case_id))}</b>",
            body_style,
        )
    )

    story.append(Spacer(1, 3 * mm))

    # --------------------------------------------------------
    # CASE INFORMATION
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "Case Information",
        section_style,
    )

    case_data = [
        [
            Paragraph("<b>Case ID</b>", body_style),
            Paragraph(
                pdf_escape(case_id),
                body_style,
            ),
        ],
        [
            Paragraph("<b>Case</b>", body_style),
            Paragraph(
                pdf_escape(
                    case.get("title")
                ),
                body_style,
            ),
        ],
        [
            Paragraph("<b>Department</b>", body_style),
            Paragraph(
                pdf_escape(
                    case.get("department")
                ),
                body_style,
            ),
        ],
        [
            Paragraph("<b>Amount</b>", body_style),
            Paragraph(
                pdf_escape(
                    format_amount(
                        case.get("amount", 0)
                    )
                ),
                body_style,
            ),
        ],
        [
            Paragraph("<b>Status</b>", body_style),
            Paragraph(
                pdf_escape(
                    safe_text(
                        case.get(
                            "status"
                        )
                    ).upper()
                ),
                body_style,
            ),
        ],
        [
            Paragraph("<b>Created</b>", body_style),
            Paragraph(
                pdf_escape(
                    format_timestamp(
                        case.get("created_at")
                    )
                ),
                body_style,
            ),
        ],
    ]

    case_table = Table(
        case_data,
        colWidths=[
            40 * mm,
            135 * mm,
        ],
    )

    case_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.grey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.whitesmoke,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(case_table)

    # --------------------------------------------------------
    # EVIDENCE GATE
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "Evidence Gate",
        section_style,
    )

    gate_status = (
        "PASSED"
        if evidence_gate.get(
            "complete",
            False,
        )
        else "INCOMPLETE"
    )

    story.append(
        Paragraph(
            f"<b>Status:</b> "
            f"{escape(gate_status)}",
            body_style,
        )
    )

    if missing_requirements:
        story.append(
            Paragraph(
                "<b>Missing Requirements:</b>",
                body_style,
            )
        )

        for item in missing_requirements:
            if isinstance(item, dict):
                text = safe_text(
                    item.get("name")
                )
            else:
                text = safe_text(item)

            story.append(
                Paragraph(
                    f"&bull; {pdf_escape(text)}",
                    body_style,
                )
            )

    # --------------------------------------------------------
    # POLICY REQUIREMENTS
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "Policy-Driven Requirements",
        section_style,
    )

    if requirements:
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue

            name = safe_text(
                requirement.get("name"),
                "Requirement",
            )

            status = safe_text(
                requirement.get("status"),
                "UNKNOWN",
            ).upper()

            mandatory = (
                "Mandatory"
                if requirement.get(
                    "mandatory",
                    False,
                )
                else "Conditional"
            )

            reason = safe_text(
                requirement.get("reason")
            )

            evidence_rule = safe_text(
                requirement.get(
                    "evidence_rule"
                )
            )

            minimum_count = requirement.get(
                "minimum_count"
            )

            minimum_text = ""

            if minimum_count:
                minimum_text = (
                    f" — Minimum: "
                    f"{minimum_count}"
                )

            story.append(
                Paragraph(
                    (
                        f"<b>{pdf_escape(name)}</b> — "
                        f"{escape(mandatory)} — "
                        f"{escape(status)}"
                        f"{escape(minimum_text)}"
                    ),
                    body_style,
                )
            )

            story.append(
                Paragraph(
                    (
                        f"Reason: "
                        f"{pdf_escape(reason)}"
                    ),
                    small_style,
                )
            )

            story.append(
                Paragraph(
                    (
                        "Policy / Evidence Rule: "
                        f"{pdf_escape(evidence_rule)}"
                    ),
                    small_style,
                )
            )

            story.append(
                Spacer(1, 2 * mm)
            )
    else:
        story.append(
            Paragraph(
                "No policy-driven requirements "
                "were recorded.",
                body_style,
            )
        )

    # --------------------------------------------------------
    # AI ASSESSMENT
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "AI Assessment",
        section_style,
    )

    if not review:
        story.append(
            Paragraph(
                "No completed AI assessment "
                "is available for this case.",
                body_style,
            )
        )
    else:
        recommendation = safe_text(
            review.get("recommendation"),
            "N/A",
        )
        
        if recommendation.startswith("OVERALL STATUS:"):
            synthesis_recommendation = (
                synthesis_result.get("ai_recommendation")
                or synthesis_result.get("recommendation")
            )
        
            if synthesis_recommendation:
                recommendation = safe_text(
                    synthesis_recommendation
                )

        story.append(
            Paragraph(
                (
                    "<b>AI Recommendation:</b> "
                    f"{pdf_escape(recommendation)}"
                ),
                body_style,
            )
        )

        # ----------------------------------------------------
        # Executive Summary
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Executive Summary",
                subsection_style,
            )
        )

        executive_summary = (
            synthesis_result.get(
                "executive_summary"
            )
            or synthesis_result.get(
                "summary"
            )
        )

        if executive_summary:
            add_pdf_text(
                story,
                executive_summary,
                body_style,
            )

        # ----------------------------------------------------
        # Compliance Agent
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Compliance Assessment",
                subsection_style,
            )
        )

        add_pdf_text(
            story,
            result_text(
                compliance_result
            ),
            body_style,
        )

        # ----------------------------------------------------
        # Financial Agent
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Financial Assessment",
                subsection_style,
            )
        )

        add_pdf_text(
            story,
            result_text(
                financial_result
            ),
            body_style,
        )

        # ----------------------------------------------------
        # Risk Agent
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Risk Assessment",
                subsection_style,
            )
        )

        add_pdf_text(
            story,
            result_text(
                risk_result
            ),
            body_style,
        )

        # ----------------------------------------------------
        # Selected Decision-Synthesis Sections
        #
        # IMPORTANT:
        # Do NOT print the complete synthesis here.
        # This prevents the old duplication where the entire
        # AI assessment appeared again under "Decision
        # Synthesis".
        # ----------------------------------------------------

        synthesis_sections = [
            (
                "key_findings",
                "Key Findings",
            ),
            (
                "missing_or_unclear_information",
                "Missing or Unclear Information",
            ),
            (
                "critical_policy_control_issues",
                "Critical Policy / Control Issues",
            ),
            (
                "critical_policy_issues",
                "Critical Policy / Control Issues",
            ),
            (
                "required_actions_before_final_decision",
                "Required Actions Before Final Decision",
            ),
            (
                "required_actions",
                "Required Actions",
            ),
        ]

        already_rendered = set()

        for key, title in synthesis_sections:
            if title in already_rendered:
                continue

            value = synthesis_result.get(key)

            if value is None:
                continue

            already_rendered.add(title)

            story.append(
                Paragraph(
                    escape(title),
                    subsection_style,
                )
            )

            if isinstance(value, list):
                for index, item in enumerate(
                    value,
                    start=1,
                ):
                    story.append(
                        Paragraph(
                            (
                                f"{index}. "
                                f"{pdf_escape(item)}"
                            ),
                            body_style,
                        )
                    )
            else:
                add_pdf_text(
                    story,
                    value,
                    body_style,
                )

        human_review_required = (
            synthesis_result.get(
                "human_review_required"
            )
        )

        if human_review_required is None:
            human_review_required = (
                review.get(
                    "human_review_required"
                )
            )

        if human_review_required is not None:
            story.append(
                Paragraph(
                    (
                        "<b>Human Review Required:</b> "
                        f"{'YES' if human_review_required else 'NO'}"
                    ),
                    body_style,
                )
            )

    # --------------------------------------------------------
    # HUMAN DECISION
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "Human Decision",
        section_style,
    )

    if decision:
        decision_value = safe_text(
            decision.get("decision"),
            "N/A",
        )

        story.append(
            Paragraph(
                (
                    "<b>Final Decision:</b> "
                    f"{pdf_escape(decision_value.title())}"
                ),
                body_style,
            )
        )

        story.append(
            Paragraph(
                (
                    "<b>Decision Date:</b> "
                    f"{pdf_escape(format_timestamp(decision.get('created_at')))}"
                ),
                body_style,
            )
        )

        comments = decision.get(
            "comments"
        )

        if comments:
            story.append(
                Paragraph(
                    (
                        "<b>Comments:</b> "
                        f"{pdf_escape(comments)}"
                    ),
                    body_style,
                )
            )
    else:
        story.append(
            Paragraph(
                "No human decision has been recorded "
                "for this case.",
                body_style,
            )
        )

    # --------------------------------------------------------
    # WORKFLOW
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "AI Workflow Checkpoints",
        section_style,
    )

    if steps:
        workflow_data = [
            [
                Paragraph(
                    "<b>Step</b>",
                    small_style,
                ),
                Paragraph(
                    "<b>Status</b>",
                    small_style,
                ),
                Paragraph(
                    "<b>Provider</b>",
                    small_style,
                ),
                Paragraph(
                    "<b>Model</b>",
                    small_style,
                ),
            ]
        ]

        for step in steps:
            workflow_data.append(
                [
                    Paragraph(
                        pdf_escape(
                            step.get(
                                "step_name"
                            )
                        ),
                        small_style,
                    ),
                    Paragraph(
                        pdf_escape(
                            safe_text(
                                step.get(
                                    "status"
                                )
                            ).upper()
                        ),
                        small_style,
                    ),
                    Paragraph(
                        pdf_escape(
                            step.get(
                                "provider"
                            )
                        ),
                        small_style,
                    ),
                    Paragraph(
                        pdf_escape(
                            step.get(
                                "model"
                            )
                        ),
                        small_style,
                    ),
                ]
            )

        workflow_table = Table(
            workflow_data,
            colWidths=[
                50 * mm,
                30 * mm,
                40 * mm,
                55 * mm,
            ],
            repeatRows=1,
        )

        workflow_table.setStyle(
            TableStyle(
                [
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.grey,
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.whitesmoke,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                ]
            )
        )

        story.append(workflow_table)

    else:
        story.append(
            Paragraph(
                "No AI workflow checkpoints were recorded.",
                body_style,
            )
        )

    # --------------------------------------------------------
    # AUDIT TRAIL
    # --------------------------------------------------------

    add_pdf_section_title(
        story,
        "Audit Trail",
        section_style,
    )

    if audit_logs:
        for log in audit_logs:
            timestamp = format_timestamp(
                log.get("created_at")
            )

            action = safe_text(
                log.get("action"),
                "AUDIT_EVENT",
            )

            description = safe_text(
                log.get("description"),
                "",
            )

            story.append(
                Paragraph(
                    (
                        f"<b>{pdf_escape(timestamp)} "
                        f"— {pdf_escape(action)}</b>"
                    ),
                    body_style,
                )
            )

            if description:
                story.append(
                    Paragraph(
                        pdf_escape(description),
                        small_style,
                    )
                )

            metadata = parse_json(
                log.get("metadata"),
                {},
            )

            if metadata:
                story.append(
                    Paragraph(
                        pdf_escape(
                            json.dumps(
                                metadata,
                                ensure_ascii=False,
                            )
                        ),
                        small_style,
                    )
                )

            story.append(
                Spacer(1, 2 * mm)
            )
    else:
        story.append(
            Paragraph(
                "No audit events were recorded.",
                body_style,
            )
        )

    # --------------------------------------------------------
    # DISCLAIMER
    # --------------------------------------------------------

    story.append(
        Spacer(1, 5 * mm)
    )

    story.append(
        Paragraph(
            (
                "<b>AegisAI — Advisory Notice:</b> "
                "AI recommendations are advisory. "
                "Human decisions are authoritative."
            ),
            small_style,
        )
    )

    # --------------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------------

    document.build(story)

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# DOWNLOAD PDF
# ============================================================

st.markdown("---")
st.subheader("Download Report")

if review:
    try:
        pdf_bytes = generate_pdf()

        filename = (
            f"AegisAI_Case_"
            f"{case_id}_Approval_Report.pdf"
        )

        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )

        st.caption(
            f"Report for Case #{case_id}: "
            f"{safe_text(case.get('title'))}"
        )

    except Exception as exc:
        st.error(
            f"Unable to generate PDF report: {exc}"
        )
else:
    st.warning(
        "A PDF report cannot be generated until "
        "an AI review is available for this case."
    )


# ============================================================
# BOTTOM NAVIGATION
# ============================================================

st.markdown("---")

nav_col1, nav_col2 = st.columns(2)

with nav_col1:
    if st.button(
        "← Previous: Case History",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/5_Case_History.py"
        )

with nav_col2:
    if st.button(
        "Back to Dashboard",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/1_Dashboard.py"
        )
