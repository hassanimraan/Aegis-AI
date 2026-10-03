import html
from io import BytesIO

import streamlit as st

from database.supabase_client import get_supabase

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


st.set_page_config(
    page_title="Report - AegisAI",
    page_icon="📄",
    layout="wide",
)


# =========================================================
# AUTHENTICATION
# =========================================================

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning(
        "Please log in from the main AegisAI page."
    )
    st.stop()


# =========================================================
# SUPABASE
# =========================================================

try:
    supabase = get_supabase()

except Exception as e:
    st.error(
        f"Unable to connect to Supabase: {e}"
    )
    st.stop()


# =========================================================
# PAGE HEADER
# =========================================================

st.title("📄 Approval Report")

st.write(
    "View and download the complete AI-assisted approval "
    "and compliance report."
)

st.divider()


# =========================================================
# HELPERS
# =========================================================

def format_amount(value):
    try:
        return f"PKR {float(value):,.0f}"
    except (TypeError, ValueError):
        return "PKR N/A"


def safe_text(value, default="N/A"):
    if value is None or value == "":
        return default
    return str(value)


def extract_ai_text(value):
    """
    AI agent results may be stored as either:
    - a router result dictionary containing 'text'
    - plain text
    """
    if isinstance(value, dict):
        return str(
            value.get(
                "text",
                ""
            )
        )

    return str(
        value
        if value is not None
        else ""
    )


def pdf_text(value):
    """
    Safely convert arbitrary text to ReportLab-compatible
    escaped HTML/XML text.
    """

    if value is None:
        return ""

    return (
        html.escape(
            str(value)
        )
        .replace(
            "\n",
            "<br/>"
        )
    )


# =========================================================
# LOAD CASES
# =========================================================

try:
    response = (
        supabase
        .table("cases")
        .select("*")
        .eq(
            "user_id",
            st.session_state["user"].id
        )
        .order(
            "created_at",
            desc=True
        )
        .execute()
    )

    cases = response.data or []

except Exception as e:
    st.error(
        f"Unable to load cases: {e}"
    )
    st.stop()


if not cases:
    st.info(
        "No approval cases are available."
    )
    st.stop()


# =========================================================
# SELECT CASE
# =========================================================

case_options = {}

for case_item in cases:

    title = case_item.get(
        "title",
        "Untitled"
    )

    amount_display = format_amount(
        case_item.get(
            "amount",
            0
        )
    )

    label = (
        f"{title} — "
        f"{amount_display}"
    )

    case_options[label] = case_item


selected_label = st.selectbox(
    "Select Case",
    list(case_options.keys())
)

case = case_options[selected_label]

case_id = case["id"]


# =========================================================
# LOAD AI REVIEW
# =========================================================

try:
    review_response = (
        supabase
        .table("ai_reviews")
        .select("*")
        .eq(
            "case_id",
            case_id
        )
        .order(
            "created_at",
            desc=True
        )
        .limit(1)
        .execute()
    )

    reviews = review_response.data or []

except Exception:
    reviews = []


review = (
    reviews[0]
    if reviews
    else {}
)


# =========================================================
# LOAD WORKFLOW CHECKPOINTS
# =========================================================

STEP_DEFINITIONS = [
    ("RAG", "Policy Retrieval"),
    ("COMPLIANCE", "Compliance Agent"),
    ("FINANCIAL", "Financial Agent"),
    ("RISK", "Risk Agent"),
    ("SYNTHESIS", "Decision Synthesizer"),
    ("EVIDENCE", "Evidence Gate"),
]


try:
    steps_response = (
        supabase
        .table("ai_review_steps")
        .select("*")
        .eq(
            "case_id",
            case_id
        )
        .order(
            "step_order",
            desc=False
        )
        .execute()
    )

    review_steps = steps_response.data or []

except Exception:
    review_steps = []


step_map = {
    step.get("step_name"): step
    for step in review_steps
}


# =========================================================
# LOAD HUMAN DECISION
# =========================================================

try:
    decision_response = (
        supabase
        .table("decisions")
        .select("*")
        .eq(
            "case_id",
            case_id
        )
        .order(
            "created_at",
            desc=True
        )
        .limit(1)
        .execute()
    )

    decisions = decision_response.data or []

except Exception:
    decisions = []


decision = (
    decisions[0]
    if decisions
    else {}
)


# =========================================================
# LOAD AUDIT LOGS
# =========================================================

try:
    audit_response = (
        supabase
        .table("audit_logs")
        .select("*")
        .eq(
            "case_id",
            case_id
        )
        .order(
            "created_at",
            desc=True
        )
        .execute()
    )

    audit_logs = audit_response.data or []

except Exception:
    audit_logs = []


# =========================================================
# EVIDENCE GATE
# =========================================================

evidence_gate = {}

if review:

    evidence_gate = (
        review.get(
            "evidence_gate",
            {}
        )
        or {}
    )

    if isinstance(
        evidence_gate,
        str
    ):
        evidence_gate = {}


gate_complete = bool(
    evidence_gate.get(
        "complete",
        False
    )
)

missing_requirements = (
    evidence_gate.get(
        "missing_requirements",
        []
    )
    or []
)

requirements = (
    review.get(
        "requirements",
        []
    )
    or []
)


# =========================================================
# CASE INFORMATION
# =========================================================

st.subheader("📌 Case Information")

col1, col2, col3 = st.columns(3)

with col1:

    st.write(
        f"**Case:** "
        f"{safe_text(case.get('title'))}"
    )

    st.write(
        f"**Department:** "
        f"{safe_text(case.get('department'))}"
    )

with col2:

    st.write(
        f"**Amount:** "
        f"{format_amount(case.get('amount', 0))}"
    )

    st.write(
        f"**Status:** "
        f"{safe_text(case.get('status'))}"
    )

with col3:

    st.write(
        f"**Created:** "
        f"{safe_text(case.get('created_at'))}"
    )


st.divider()


# =========================================================
# AI WORKFLOW STATUS
# =========================================================

st.subheader("⚙️ AI Review Workflow")

if review_steps:

    workflow_cols = st.columns(3)

    for index, (step_name, label) in enumerate(
        STEP_DEFINITIONS
    ):

        step = step_map.get(
            step_name,
            {}
        )

        status = (
            step.get(
                "status",
                "PENDING"
            )
            or "PENDING"
        ).upper()

        provider = step.get(
            "provider"
        )

        model = step.get(
            "model"
        )

        with workflow_cols[index % 3]:

            if status == "COMPLETED":

                st.success(
                    f"✅ {label}\n\n"
                    f"COMPLETED"
                )

            elif status == "RUNNING":

                st.info(
                    f"🔄 {label}\n\n"
                    f"RUNNING"
                )

            elif status == "FAILED":

                st.error(
                    f"❌ {label}\n\n"
                    f"FAILED"
                )

            else:

                st.warning(
                    f"⏳ {label}\n\n"
                    f"{status}"
                )

            if provider or model:

                provider_text = (
                    provider
                    if provider
                    else "N/A"
                )

                model_text = (
                    model
                    if model
                    else "N/A"
                )

                st.caption(
                    f"{provider_text} · "
                    f"{model_text}"
                )

else:

    st.info(
        "No AI review workflow has been completed "
        "for this case."
    )


st.divider()


# =========================================================
# EVIDENCE GATE
# =========================================================

st.subheader("🛡️ Evidence Gate")

if not review:

    st.warning(
        "Evidence requirements cannot be evaluated "
        "because no AI review is available."
    )

else:

    if gate_complete:

        st.success(
            "✅ Evidence Gate PASSED — all mandatory "
            "policy-driven evidence requirements are satisfied."
        )

    else:

        st.error(
            "🔒 Evidence Gate NOT PASSED — mandatory "
            "policy-driven evidence is incomplete."
        )

        if missing_requirements:

            st.write(
                "**Missing / Incomplete Requirements:**"
            )

            for item in missing_requirements:

                if isinstance(item, dict):

                    description = (
                        item.get(
                            "description"
                        )
                        or item.get(
                            "requirement"
                        )
                        or item.get(
                            "name"
                        )
                        or "Mandatory evidence requirement"
                    )

                    policy_reference = (
                        item.get(
                            "policy_reference"
                        )
                        or item.get(
                            "policy"
                        )
                        or ""
                    )

                    if policy_reference:

                        st.write(
                            f"- {description} "
                            f"({policy_reference})"
                        )

                    else:

                        st.write(
                            f"- {description}"
                        )

                else:

                    st.write(
                        f"- {item}"
                    )

        else:

            st.write(
                "The evidence gate has not been satisfied."
            )


st.divider()


# =========================================================
# AI ASSESSMENT
# =========================================================

st.subheader("🤖 AI Assessment")

if review:

    recommendation = safe_text(
        review.get(
            "recommendation"
        )
    )

    st.info(
        f"**AI Recommendation:** "
        f"{recommendation}"
    )

    synthesis = extract_ai_text(
        review.get(
            "synthesis"
        )
    )

    if synthesis:

        st.write(
            "### Decision Synthesis"
        )

        st.write(
            synthesis
        )

else:

    st.warning(
        "No AI review is available for this case."
    )


# ---------------------------------------------------------
# Agent Assessments
# ---------------------------------------------------------

if review:

    with st.expander(
        "Compliance Assessment"
    ):

        compliance_text = extract_ai_text(
            review.get(
                "compliance"
            )
        )

        if compliance_text:
            st.write(
                compliance_text
            )
        else:
            st.info(
                "No Compliance Agent result available."
            )


    with st.expander(
        "Financial Assessment"
    ):

        financial_text = extract_ai_text(
            review.get(
                "financial"
            )
        )

        if financial_text:
            st.write(
                financial_text
            )
        else:
            st.info(
                "No Financial Agent result available."
            )


    with st.expander(
        "Risk Assessment"
    ):

        risk_text = extract_ai_text(
            review.get(
                "risk"
            )
        )

        if risk_text:
            st.write(
                risk_text
            )
        else:
            st.info(
                "No Risk Agent result available."
            )


st.divider()


# =========================================================
# POLICY REQUIREMENTS
# =========================================================

if requirements:

    st.subheader(
        "📋 Policy-Driven Requirements"
    )

    for requirement in requirements:

        if isinstance(
            requirement,
            dict
        ):

            description = (
                requirement.get(
                    "description"
                )
                or requirement.get(
                    "requirement"
                )
                or requirement.get(
                    "name"
                )
                or "Requirement"
            )

            mandatory = requirement.get(
                "mandatory"
            )

            conditional = requirement.get(
                "conditional"
            )

            policy_reference = (
                requirement.get(
                    "policy_reference"
                )
                or requirement.get(
                    "policy"
                )
                or ""
            )

            status = requirement.get(
                "status"
            )

            line = f"**{description}**"

            if mandatory is True:
                line += " — Mandatory"

            elif conditional is True:
                line += " — Conditional"

            if status:
                line += f" — {status}"

            if policy_reference:
                line += (
                    f"  \nPolicy: "
                    f"{policy_reference}"
                )

            st.markdown(
                line
            )

        else:

            st.write(
                f"- {requirement}"
            )


st.divider()


# =========================================================
# HUMAN DECISION
# =========================================================

st.subheader("👤 Human Decision")

if decision:

    decision_value = safe_text(
        decision.get(
            "decision"
        )
    )

    col1, col2 = st.columns(2)

    with col1:

        st.success(
            f"**Final Decision:** "
            f"{decision_value}"
        )

    with col2:

        st.write(
            f"**Decision Date:** "
            f"{safe_text(decision.get('created_at'))}"
        )

    st.write(
        f"**Reviewer Comments:** "
        f"{decision.get('comments') or 'None'}"
    )

else:

    st.warning(
        "No human decision has been recorded."
    )

    if review and not gate_complete:

        st.info(
            "Human decision remains locked because "
            "the Evidence Gate has not been satisfied."
        )

    elif not review:

        st.info(
            "Complete the AI review before proceeding "
            "to human decision."
        )

    else:

        st.info(
            "Evidence requirements are satisfied, "
            "but no human decision has been recorded yet."
        )


st.divider()


# =========================================================
# AUDIT TRAIL
# =========================================================

st.subheader("📝 Audit Trail")

if audit_logs:

    for log in audit_logs:

        st.write(
            f"**{safe_text(log.get('created_at'))}** — "
            f"{safe_text(log.get('action'))}"
        )

        if log.get("details"):

            st.caption(
                str(
                    log.get(
                        "details"
                    )
                )
            )

else:

    st.info(
        "No audit records available."
    )


st.divider()


# =========================================================
# PDF REPORT GENERATOR
# =========================================================

def generate_pdf():

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    story = []

    story.append(
        Paragraph(
            "AegisAI — Approval & Compliance Report",
            title_style,
        )
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # CASE INFORMATION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Case Information</b>",
            styles["Heading2"],
        )
    )

    case_data = [
        [
            "Case",
            pdf_text(
                case.get(
                    "title",
                    "N/A"
                )
            ),
        ],
        [
            "Department",
            pdf_text(
                case.get(
                    "department",
                    "N/A"
                )
            ),
        ],
        [
            "Amount",
            pdf_text(
                format_amount(
                    case.get(
                        "amount",
                        0
                    )
                )
            ),
        ],
        [
            "Status",
            pdf_text(
                case.get(
                    "status",
                    "N/A"
                )
            ),
        ],
        [
            "Created",
            pdf_text(
                case.get(
                    "created_at",
                    "N/A"
                )
            ),
        ],
    ]

    table = Table(
        case_data,
        colWidths=[130, 350],
    )

    table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
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
                colors.lightgrey,
            ),
            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "Helvetica-Bold",
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
        ])
    )

    story.append(
        table
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # EVIDENCE GATE
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Evidence Gate</b>",
            styles["Heading2"],
        )
    )

    gate_status = (
        "PASSED"
        if gate_complete
        else "NOT PASSED"
    )

    story.append(
        Paragraph(
            (
                "<b>Status:</b> "
                f"{pdf_text(gate_status)}"
            ),
            styles["BodyText"],
        )
    )

    if missing_requirements:

        story.append(
            Spacer(1, 8)
        )

        story.append(
            Paragraph(
                "<b>Missing / Incomplete Requirements:</b>",
                styles["BodyText"],
            )
        )

        for item in missing_requirements:

            if isinstance(
                item,
                dict
            ):

                description = (
                    item.get(
                        "description"
                    )
                    or item.get(
                        "requirement"
                    )
                    or item.get(
                        "name"
                    )
                    or "Mandatory evidence requirement"
                )

                policy_reference = (
                    item.get(
                        "policy_reference"
                    )
                    or item.get(
                        "policy"
                    )
                    or ""
                )

                text = str(
                    description
                )

                if policy_reference:

                    text += (
                        f" ({policy_reference})"
                    )

            else:

                text = str(item)

            story.append(
                Paragraph(
                    f"• {pdf_text(text)}",
                    styles["BodyText"],
                )
            )


    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # AI ASSESSMENT
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>AI Assessment</b>",
            styles["Heading2"],
        )
    )

    recommendation = safe_text(
        review.get(
            "recommendation"
        )
    )

    story.append(
        Paragraph(
            (
                "<b>AI Recommendation:</b> "
                f"{pdf_text(recommendation)}"
            ),
            styles["BodyText"],
        )
    )

    story.append(
        Spacer(1, 10)
    )

    synthesis = extract_ai_text(
        review.get(
            "synthesis"
        )
    )

    if synthesis:

        story.append(
            Paragraph(
                "<b>Decision Synthesis</b>",
                styles["Heading3"],
            )
        )

        story.append(
            Paragraph(
                pdf_text(
                    synthesis
                ),
                styles["BodyText"],
            )
        )

    else:

        story.append(
            Paragraph(
                "No AI synthesis available.",
                styles["BodyText"],
            )
        )


    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # HUMAN DECISION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Human Decision</b>",
            styles["Heading2"],
        )
    )

    if decision:

        story.append(
            Paragraph(
                (
                    "<b>Final Decision:</b> "
                    f"{pdf_text(decision.get('decision', 'N/A'))}"
                ),
                styles["BodyText"],
            )
        )

        story.append(
            Paragraph(
                (
                    "<b>Decision Date:</b> "
                    f"{pdf_text(decision.get('created_at', 'N/A'))}"
                ),
                styles["BodyText"],
            )
        )

        story.append(
            Paragraph(
                (
                    "<b>Comments:</b> "
                    f"{pdf_text(decision.get('comments') or 'None')}"
                ),
                styles["BodyText"],
            )
        )

    else:

        story.append(
            Paragraph(
                "No human decision has been recorded.",
                styles["BodyText"],
            )
        )


    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # WORKFLOW STATUS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>AI Workflow Checkpoints</b>",
            styles["Heading2"],
        )
    )

    workflow_data = [
        [
            "Step",
            "Status",
            "Provider",
            "Model",
        ]
    ]

    for step_name, label in STEP_DEFINITIONS:

        step = step_map.get(
            step_name,
            {}
        )

        workflow_data.append(
            [
                label,
                safe_text(
                    step.get(
                        "status",
                        "PENDING"
                    )
                ),
                safe_text(
                    step.get(
                        "provider"
                    )
                ),
                safe_text(
                    step.get(
                        "model"
                    )
                ),
            ]
        )

    workflow_table = Table(
        workflow_data,
        colWidths=[
            150,
            90,
            90,
            150,
        ],
        repeatRows=1,
    )

    workflow_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey,
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey,
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ])
    )

    story.append(
        workflow_table
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # AUDIT TRAIL
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Audit Trail</b>",
            styles["Heading2"],
        )
    )

    if audit_logs:

        for log in audit_logs:

            text = (
                f"{log.get('created_at', 'N/A')} — "
                f"{log.get('action', 'N/A')} — "
                f"{log.get('details', '')}"
            )

            story.append(
                Paragraph(
                    pdf_text(text),
                    styles["BodyText"],
                )
            )

            story.append(
                Spacer(1, 5)
            )

    else:

        story.append(
            Paragraph(
                "No audit records available.",
                styles["BodyText"],
            )
        )


    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # DISCLAIMER
    # -----------------------------------------------------

    story.append(
        Paragraph(
            (
                "AegisAI — AI recommendations are advisory. "
                "Human decisions are authoritative."
            ),
            styles["Italic"],
        )
    )

    document.build(
        story
    )

    buffer.seek(0)

    return buffer


# =========================================================
# DOWNLOAD PDF
# =========================================================

st.subheader("📥 Download Report")

pdf_file = generate_pdf()

st.download_button(
    label="Download PDF Report",
    data=pdf_file,
    file_name="AegisAI_Approval_Report.pdf",
    mime="application/pdf",
    type="primary",
    use_container_width=True,
)


# =========================================================
# PAGE NAVIGATION
# =========================================================

st.divider()

nav_left, nav_right = st.columns(2)

with nav_left:

    if st.button(
        "← Case History",
        use_container_width=True,
        key="report_previous",
    ):

        st.switch_page(
            "pages/5_Case_History.py"
        )


with nav_right:

    if st.button(
        "Back to Dashboard",
        use_container_width=True,
        key="report_dashboard",
    ):

        st.switch_page(
            "pages/1_Dashboard.py"
        )
