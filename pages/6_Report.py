import json
import re
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


def has_value(value):
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (dict, list)):
        return len(value) > 0

    return True


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


# ============================================================
# AI REVIEW ROW MERGING
# ============================================================

AI_RESULT_FIELDS = [
    "compliance_result",
    "financial_result",
    "risk_result",
    "synthesis",
]

AI_OPTIONAL_FIELDS = [
    "recommendation",
    "human_review_required",
    "requirements",
    "evidence_gate",
]


def merge_ai_review_rows(reviews):
    """
    Merge all AI review rows for the selected case.

    Newest non-empty value wins for each field.
    """

    if not reviews:
        return None

    merged = dict(reviews[0])

    for field in AI_RESULT_FIELDS:
        for row in reviews:
            value = row.get(field)

            if has_value(value):
                merged[field] = value
                break

    for field in AI_OPTIONAL_FIELDS:
        for row in reviews:
            value = row.get(field)

            if has_value(value):
                merged[field] = value
                break

    return merged


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def normalize_result(value):
    """
    Preserve plain-text AI output.

    Supports:
    - plain text
    - JSON strings
    - dictionaries
    - lists
    """

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        return {"items": value}

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return {}

        parsed = parse_json(text, None)

        if isinstance(parsed, dict):
            return parsed

        if isinstance(parsed, list):
            return {"items": parsed}

        return {"text": text}

    return {"text": str(value)}


# ============================================================
# RESULT TO TEXT
# ============================================================

def result_text(result):
    """
    Convert any AI result into readable text.
    """

    if result is None:
        return "No assessment available."

    if isinstance(result, str):
        text = result.strip()

        if not text:
            return "No assessment available."

        parsed = parse_json(text, None)

        if isinstance(parsed, (dict, list)):
            return result_text(parsed)

        return text

    if isinstance(result, list):

        if not result:
            return "No assessment available."

        lines = []

        for index, item in enumerate(result, start=1):

            if isinstance(item, dict):
                lines.append(
                    f"{index}. {result_text(item)}"
                )
            else:
                lines.append(
                    f"{index}. {safe_text(item)}"
                )

        return "\n".join(lines)

    if not isinstance(result, dict):
        return safe_text(result)

    if result.get("text"):
        return safe_text(
            result.get("text"),
            "No assessment available.",
        )

    if "items" in result:
        return result_text(result.get("items"))

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

                    if isinstance(item, dict):
                        sections.append(
                            f"• {result_text(item)}"
                        )
                    else:
                        sections.append(
                            f"• {safe_text(item)}"
                        )

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

    fallback = []

    for key, value in result.items():

        if value is None:
            continue

        if isinstance(value, list):

            fallback.append(
                f"{key.replace('_', ' ').title()}:"
            )

            for item in value:

                if isinstance(item, dict):
                    fallback.append(
                        f"• {result_text(item)}"
                    )
                else:
                    fallback.append(
                        f"• {safe_text(item)}"
                    )

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


# ============================================================
# AI RESULT EXTRACTION
# ============================================================

def extract_assessment(review, field_name):
    """
    IMPORTANT:
    AI assessment fields are stored as plain text in Supabase.

    Return the raw database value directly instead of forcing
    it through result_text().
    """

    if not review:
        return ""

    field = f"{field_name}_result"

    value = review.get(field)

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (dict, list)):
        return result_text(value)

    return str(value).strip()


def extract_synthesis(review):
    """
    Return the raw synthesis stored in Supabase.
    """

    if not review:
        return ""

    value = review.get("synthesis")

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (dict, list)):
        return result_text(value)

    return str(value).strip()


# ============================================================
# RECOMMENDATION EXTRACTION
# ============================================================

def clean_heading(line):

    if line is None:
        return ""

    text = str(line).strip()

    text = re.sub(
        r"^#+\s*",
        "",
        text,
    )

    text = text.strip("*_ ")

    return text.strip()


def extract_recommendation_from_text(text):

    if not text:
        return None

    lines = str(text).splitlines()

    for index, line in enumerate(lines):

        cleaned = line.strip()

        if not cleaned:
            continue

        normalized = clean_heading(cleaned)

        if normalized.upper() == "AI RECOMMENDATION:":

            for next_line in lines[index + 1:]:

                value = next_line.strip()

                if not value:
                    continue

                value = clean_heading(value)

                if value:
                    return value

        match = re.match(
            r"^(?:#+\s*)?(?:\*\*)?\s*AI\s+RECOMMENDATION\s*:?\s*(?:\*\*)?\s*(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:

            value = match.group(1).strip()
            value = value.strip("*_ ")

            if value:
                return value

        match = re.match(
            r"^(?:#+\s*)?(?:\*\*)?\s*RECOMMENDATION\s*:?\s*(?:\*\*)?\s*(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:

            value = match.group(1).strip()
            value = value.strip("*_ ")

            if value:
                return value

    return None


def extract_ai_recommendation(
    review,
    synthesis_result,
):

    if not review:
        return "N/A"

    if isinstance(synthesis_result, dict):

        for key in (
            "ai_recommendation",
            "recommendation",
        ):

            value = synthesis_result.get(key)

            if has_value(value):

                return safe_text(
                    value,
                    "N/A",
                )

        text = synthesis_result.get("text")

        if text:

            recommendation = (
                extract_recommendation_from_text(text)
            )

            if recommendation:
                return recommendation

    synthesis = review.get("synthesis")

    if synthesis:

        recommendation = (
            extract_recommendation_from_text(
                str(synthesis)
            )
        )

        if recommendation:
            return recommendation

    recommendation_field = review.get(
        "recommendation"
    )

    if recommendation_field:

        if isinstance(
            recommendation_field,
            dict,
        ):

            for key in (
                "ai_recommendation",
                "recommendation",
                "text",
            ):

                value = recommendation_field.get(key)

                if has_value(value):

                    return safe_text(
                        value,
                        "N/A",
                    )

        recommendation = (
            extract_recommendation_from_text(
                str(recommendation_field)
            )
        )

        if recommendation:
            return recommendation

    return "N/A"


# ============================================================
# SYNTHESIS SECTION EXTRACTION
# ============================================================

def extract_plain_text_section(
    text,
    heading,
    next_headings=None,
):

    if not text:
        return ""

    if next_headings is None:
        next_headings = []

    lines = str(text).splitlines()

    target = clean_heading(heading).upper()

    start_index = None

    for index, line in enumerate(lines):

        normalized = clean_heading(line).upper()

        if normalized == target:
            start_index = index + 1
            break

    if start_index is None:
        return ""

    normalized_next_headings = [
        clean_heading(item).upper()
        for item in next_headings
    ]

    collected = []

    for line in lines[start_index:]:

        normalized = clean_heading(line).upper()

        if normalized in normalized_next_headings:
            break

        collected.append(line)

    while collected and not collected[0].strip():
        collected.pop(0)

    while collected and not collected[-1].strip():
        collected.pop()

    return "\n".join(collected).strip()


def get_synthesis_text(synthesis_result):
    """
    Return complete synthesis text.

    Plain-text synthesis is returned directly.
    """

    if not synthesis_result:
        return ""

    if isinstance(synthesis_result, str):
        return synthesis_result.strip()

    if isinstance(synthesis_result, dict):

        text = synthesis_result.get("text")

        if has_value(text):
            return str(text).strip()

    return result_text(synthesis_result)


def get_synthesis_section(
    synthesis_result,
    section_heading,
    next_headings,
):

    structured_key_map = {

        "EXECUTIVE SUMMARY:":
            "executive_summary",

        "COMPLIANCE ASSESSMENT:":
            "compliance_assessment",

        "FINANCIAL ASSESSMENT:":
            "financial_assessment",

        "RISK ASSESSMENT:":
            "risk_assessment",

        "KEY FINDINGS:":
            "key_findings",

        "MISSING OR UNCLEAR INFORMATION:":
            "missing_or_unclear_information",

        "CRITICAL POLICY / CONTROL ISSUES:":
            "critical_policy_control_issues",

        "CRITICAL POLICY / CONTROL ISSUES":
            "critical_policy_control_issues",

        "RECOMMENDATION REASON:":
            "recommendation_reason",

        "REQUIRED ACTIONS BEFORE FINAL DECISION:":
            "required_actions_before_final_decision",

        "HUMAN REVIEW REQUIRED:":
            "human_review_required",
    }

    if isinstance(
        synthesis_result,
        dict,
    ):

        structured_key = (
            structured_key_map.get(
                clean_heading(
                    section_heading
                ).upper()
            )
        )

        if structured_key:

            value = synthesis_result.get(
                structured_key
            )

            if has_value(value):
                return value

    text = get_synthesis_text(
        synthesis_result
    )

    return extract_plain_text_section(
        text,
        section_heading,
        next_headings,
    )


# ============================================================
# STREAMLIT DISPLAY
# ============================================================

def display_multiline_text(text):

    if text is None or not str(text).strip():

        st.write(
            "No assessment available."
        )

        return

    if isinstance(
        text,
        (dict, list),
    ):

        text = result_text(text)

    for line in str(text).splitlines():

        line = line.strip()

        if not line:
            st.write("")
            continue

        if line.startswith("•"):
            st.markdown(line)

        elif line.startswith("-"):
            st.markdown(line)

        elif (
            len(line) >= 2
            and line[0].isdigit()
            and line[1] == "."
        ):

            st.markdown(line)

        else:
            st.write(line)


# ============================================================
# PDF HELPERS
# ============================================================

def pdf_escape(value):
    return escape(
        safe_text(value)
    ).replace(
        "\n",
        "<br/>",
    )


def add_pdf_section_title(
    story,
    title,
    style,
):

    story.append(
        Paragraph(
            escape(title),
            style,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )


def add_pdf_text(
    story,
    text,
    style,
):

    if text is None:
        return

    if isinstance(text, dict):
        text = result_text(text)

    if isinstance(text, list):

        for index, item in enumerate(
            text,
            start=1,
        ):

            story.append(
                Paragraph(
                    (
                        f"{index}. "
                        f"{pdf_escape(item)}"
                    ),
                    style,
                )
            )

            story.append(
                Spacer(
                    1,
                    1.5 * mm,
                )
            )

        return

    text = str(text)

    if not text.strip():
        return

    for line in text.splitlines():

        line = line.strip()

        if not line:

            story.append(
                Spacer(
                    1,
                    2 * mm,
                )
            )

            continue

        story.append(
            Paragraph(
                pdf_escape(line).replace(
                    "•",
                    "&bull;",
                ),
                style,
            )
        )

        story.append(
            Spacer(
                1,
                1.5 * mm,
            )
        )


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:

    st.markdown("## 🛡️ AegisAI")

    st.caption(
        "Approval & Compliance System"
    )

    st.markdown("---")

    st.markdown("### Navigation")

    if st.button(
        "Dashboard",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/1_Dashboard.py"
        )

    if st.button(
        "Create Approval Case",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/2_Create_Case.py"
        )

    if st.button(
        "Case Review",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/3_Case_Review.py"
        )

    if st.button(
        "Decision",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/4_Decision.py"
        )

    if st.button(
        "Case History",
        use_container_width=True,
    ):
        st.switch_page(
            "pages/5_Case_History.py"
        )

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

        st.session_state.pop(
            "user",
            None,
        )

        st.switch_page(
            "app.py"
        )


# ============================================================
# PAGE HEADER
# ============================================================

st.title(
    "AegisAI — Approval & Compliance Report"
)

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

    st.error(
        f"Unable to connect to the database: {exc}"
    )

    st.stop()


# ============================================================
# LOAD USER CASES
# ============================================================

try:

    cases_response = (
        supabase
        .table("cases")
        .select("*")
        .eq(
            "user_id",
            user.id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    cases = cases_response.data or []

except Exception as exc:

    st.error(
        f"Unable to load approval cases: {exc}"
    )

    st.stop()


if not cases:

    st.info(
        "No approval cases are available."
    )

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
# LOAD ALL AI REVIEWS
# ============================================================

try:

    review_response = (
        supabase
        .table("ai_reviews")
        .select("*")
        .eq(
            "case_id",
            case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    reviews = (
        review_response.data
        or []
    )

except Exception as exc:

    st.error(
        f"Unable to load AI review: {exc}"
    )

    st.stop()


review = merge_ai_review_rows(reviews)


# ============================================================
# LOAD WORKFLOW CHECKPOINTS
# ============================================================

try:

    steps_response = (
        supabase
        .table("ai_review_steps")
        .select("*")
        .eq(
            "case_id",
            case_id,
        )
        .order(
            "step_order"
        )
        .execute()
    )

    steps = (
        steps_response.data
        or []
    )

except Exception as exc:

    st.error(
        "Unable to load AI workflow "
        f"checkpoints: {exc}"
    )

    st.stop()


# ============================================================
# LOAD HUMAN DECISION
# ============================================================

try:

    decision_response = (
        supabase
        .table("decisions")
        .select("*")
        .eq(
            "case_id",
            case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    decisions = (
        decision_response.data
        or []
    )

except Exception as exc:

    st.error(
        f"Unable to load human decision: {exc}"
    )

    st.stop()


decision = (
    decisions[0]
    if decisions
    else None
)


# ============================================================
# LOAD AUDIT TRAIL
# ============================================================

try:

    audit_response = (
        supabase
        .table("audit_logs")
        .select("*")
        .eq(
            "case_id",
            case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    audit_logs = (
        audit_response.data
        or []
    )

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

# IMPORTANT:
# These are strings because the database stores the AI
# assessment results as plain text.
compliance_result = ""
financial_result = ""
risk_result = ""
synthesis_result = ""


if review:

    requirements = parse_json(
        review.get("requirements"),
        [],
    )

    if not isinstance(
        requirements,
        list,
    ):
        requirements = []

    evidence_gate = parse_json(
        review.get("evidence_gate"),
        {},
    )

    if not isinstance(
        evidence_gate,
        dict,
    ):
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

    synthesis_result = extract_synthesis(
        review
    )


# ============================================================
# CASE INFORMATION
# ============================================================

st.markdown("---")

st.subheader("Case Information")

case_col1, case_col2, case_col3, case_col4 = (
    st.columns(4)
)

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
            case.get("department")
        ),
    )

with case_col4:

    st.metric(
        "Amount",
        format_amount(
            case.get(
                "amount",
                0,
            )
        ),
    )

st.write(
    f"**Case:** "
    f"{safe_text(case.get('title'))}"
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
    evidence_gate.get(
        "complete",
        False,
    )
)

missing_requirements = (
    evidence_gate.get(
        "missing",
        [],
    )
)

if not isinstance(
    missing_requirements,
    list,
):
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
                f"• "
                f"{safe_text(item.get('name'))}"
            )

        else:

            st.write(
                f"• {safe_text(item)}"
            )


# ============================================================
# POLICY-DRIVEN REQUIREMENTS
# ============================================================

st.markdown("---")

st.subheader(
    "Policy-Driven Requirements"
)

if requirements:

    for requirement in requirements:

        if not isinstance(
            requirement,
            dict,
        ):
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
            requirement.get("evidence_rule")
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

        st.markdown(
            f"**{name}** — "
            f"{mandatory} — "
            f"{status}"
            f"{minimum_text}"
        )

        st.caption(
            f"Reason: {reason}"
        )

        st.caption(
            "Policy / Evidence Rule: "
            f"{evidence_rule}"
        )

else:

    st.info(
        "No policy-driven requirements "
        "were recorded."
    )


# ============================================================
# AI ASSESSMENT
# ============================================================

st.markdown("---")

st.subheader("AI Assessment")

if not review:

    st.warning(
        "No completed AI assessment is "
        "available for this case."
    )

else:

    # ========================================================
    # AI RECOMMENDATION
    # ========================================================

    recommendation = (
        extract_ai_recommendation(
            review,
            synthesis_result,
        )
    )

    st.markdown(
        "**AI Recommendation:** "
        f"{recommendation}"
    )

    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    st.markdown("### Executive Summary")

    executive_summary = (
        get_synthesis_section(
            synthesis_result,
            "EXECUTIVE SUMMARY:",
            [
                "COMPLIANCE ASSESSMENT:",
                "FINANCIAL ASSESSMENT:",
                "RISK ASSESSMENT:",
                "KEY FINDINGS:",
            ],
        )
    )

    if executive_summary:

        display_multiline_text(
            executive_summary
        )

    else:

        st.info(
            "No separate executive summary "
            "was recorded."
        )

    # ========================================================
    # COMPLIANCE
    # ========================================================

    st.markdown("### Compliance Assessment")

    # IMPORTANT:
    # Display raw AI result directly.
    display_multiline_text(
        compliance_result
    )

    # ========================================================
    # FINANCIAL
    # ========================================================

    st.markdown("### Financial Assessment")

    display_multiline_text(
        financial_result
    )

    # ========================================================
    # RISK
    # ========================================================

    st.markdown("### Risk Assessment")

    display_multiline_text(
        risk_result
    )

    # ========================================================
    # SYNTHESIS SECTIONS
    # ========================================================

    synthesis_section_definitions = [

        (
            "KEY FINDINGS:",
            "Key Findings",
            [
                "MISSING OR UNCLEAR INFORMATION:",
                "CRITICAL POLICY / CONTROL ISSUES:",
                "AI RECOMMENDATION:",
            ],
        ),

        (
            "MISSING OR UNCLEAR INFORMATION:",
            "Missing or Unclear Information",
            [
                "CRITICAL POLICY / CONTROL ISSUES:",
                "AI RECOMMENDATION:",
                "RECOMMENDATION REASON:",
            ],
        ),

        (
            "CRITICAL POLICY / CONTROL ISSUES:",
            "Critical Policy / Control Issues",
            [
                "AI RECOMMENDATION:",
                "RECOMMENDATION REASON:",
                "REQUIRED ACTIONS BEFORE FINAL DECISION:",
            ],
        ),

        (
            "RECOMMENDATION REASON:",
            "Recommendation Reason",
            [
                "REQUIRED ACTIONS BEFORE FINAL DECISION:",
                "HUMAN REVIEW REQUIRED:",
            ],
        ),

        (
            "REQUIRED ACTIONS BEFORE FINAL DECISION:",
            "Required Actions Before Final Decision",
            [
                "HUMAN REVIEW REQUIRED:",
            ],
        ),
    ]

    rendered_titles = set()

    for (
        section_heading,
        section_title,
        next_headings,
    ) in synthesis_section_definitions:

        if section_title in rendered_titles:
            continue

        section_value = (
            get_synthesis_section(
                synthesis_result,
                section_heading,
                next_headings,
            )
        )

        if not section_value:
            continue

        rendered_titles.add(section_title)

        st.markdown(
            f"### {section_title}"
        )

        display_multiline_text(
            section_value
        )

    # ========================================================
    # HUMAN REVIEW REQUIRED
    # ========================================================

    human_review_required = None

    if isinstance(
        synthesis_result,
        dict,
    ):

        human_review_required = (
            synthesis_result.get(
                "human_review_required"
            )
        )

        if human_review_required is None:

            plain_text_value = (
                synthesis_result.get("text")
            )

            if plain_text_value:

                human_review_required = (
                    extract_plain_text_section(
                        plain_text_value,
                        "HUMAN REVIEW REQUIRED:",
                        [],
                    )
                )

    if human_review_required is None:

        human_review_required = (
            review.get(
                "human_review_required"
            )
        )

    if human_review_required is not None:

        if isinstance(
            human_review_required,
            str,
        ):

            normalized_review_value = (
                human_review_required
                .strip()
                .upper()
            )

            human_review_required = (
                normalized_review_value
                in [
                    "YES",
                    "TRUE",
                    "1",
                ]
            )

        st.markdown(
            "**Human Review Required:** "
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
        "**Final Decision:** "
        f"{decision_value.title()}"
    )

    st.write(
        "**Decision Date:** "
        f"{format_timestamp(decision.get('created_at'))}"
    )

    comments = decision.get("comments")

    if comments:

        st.write(
            "**Comments:** "
            f"{safe_text(comments)}"
        )

else:

    st.info(
        "No human decision has been "
        "recorded for this case."
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
        "No AI workflow checkpoints "
        "were recorded."
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
            f"**{timestamp} — "
            f"{action}**"
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

    # ========================================================
    # TITLE
    # ========================================================

    story.append(
        Paragraph(
            "AegisAI — Approval & Compliance Report",
            title_style,
        )
    )

    story.append(
        Paragraph(
            (
                f"<b>Case #"
                f"{escape(safe_text(case_id))}</b>"
            ),
            body_style,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    # ========================================================
    # CASE INFORMATION
    # ========================================================

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
                pdf_escape(case.get("title")),
                body_style,
            ),
        ],

        [
            Paragraph(
                "<b>Department</b>",
                body_style,
            ),
            Paragraph(
                pdf_escape(
                    case.get("department")
                ),
                body_style,
            ),
        ],

        [
            Paragraph(
                "<b>Amount</b>",
                body_style,
            ),
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
            Paragraph(
                "<b>Status</b>",
                body_style,
            ),
            Paragraph(
                pdf_escape(
                    safe_text(
                        case.get("status")
                    ).upper()
                ),
                body_style,
            ),
        ],

        [
            Paragraph(
                "<b>Created</b>",
                body_style,
            ),
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

    # ========================================================
    # EVIDENCE GATE
    # ========================================================

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
            (
                "<b>Status:</b> "
                f"{escape(gate_status)}"
            ),
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
                    (
                        f"&bull; "
                        f"{pdf_escape(text)}"
                    ),
                    body_style,
                )
            )

    # ========================================================
    # POLICY REQUIREMENTS
    # ========================================================

    add_pdf_section_title(
        story,
        "Policy-Driven Requirements",
        section_style,
    )

    if requirements:

        for requirement in requirements:

            if not isinstance(
                requirement,
                dict,
            ):
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
                requirement.get("evidence_rule")
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
                        f"<b>"
                        f"{pdf_escape(name)}"
                        f"</b> — "
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
                        "Reason: "
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
                Spacer(
                    1,
                    2 * mm,
                )
            )

    else:

        story.append(
            Paragraph(
                (
                    "No policy-driven "
                    "requirements were recorded."
                ),
                body_style,
            )
        )

    # ========================================================
    # AI ASSESSMENT
    # ========================================================

    add_pdf_section_title(
        story,
        "AI Assessment",
        section_style,
    )

    if not review:

        story.append(
            Paragraph(
                (
                    "No completed AI assessment "
                    "is available for this case."
                ),
                body_style,
            )
        )

    else:

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        recommendation = (
            extract_ai_recommendation(
                review,
                synthesis_result,
            )
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
        # EXECUTIVE SUMMARY
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Executive Summary",
                subsection_style,
            )
        )

        executive_summary = (
            get_synthesis_section(
                synthesis_result,
                "EXECUTIVE SUMMARY:",
                [
                    "COMPLIANCE ASSESSMENT:",
                    "FINANCIAL ASSESSMENT:",
                    "RISK ASSESSMENT:",
                    "KEY FINDINGS:",
                ],
            )
        )

        if executive_summary:

            add_pdf_text(
                story,
                executive_summary,
                body_style,
            )

        else:

            story.append(
                Paragraph(
                    (
                        "No separate executive "
                        "summary was recorded."
                    ),
                    body_style,
                )
            )

        # ----------------------------------------------------
        # COMPLIANCE
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Compliance Assessment",
                subsection_style,
            )
        )

        # IMPORTANT:
        # Use raw AI assessment text.
        add_pdf_text(
            story,
            compliance_result,
            body_style,
        )

        # ----------------------------------------------------
        # FINANCIAL
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Financial Assessment",
                subsection_style,
            )
        )

        add_pdf_text(
            story,
            financial_result,
            body_style,
        )

        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Risk Assessment",
                subsection_style,
            )
        )

        add_pdf_text(
            story,
            risk_result,
            body_style,
        )

        # ----------------------------------------------------
        # SYNTHESIS SECTIONS
        # ----------------------------------------------------

        synthesis_section_definitions = [

            (
                "KEY FINDINGS:",
                "Key Findings",
                [
                    "MISSING OR UNCLEAR INFORMATION:",
                    "CRITICAL POLICY / CONTROL ISSUES:",
                    "AI RECOMMENDATION:",
                ],
            ),

            (
                "MISSING OR UNCLEAR INFORMATION:",
                "Missing or Unclear Information",
                [
                    "CRITICAL POLICY / CONTROL ISSUES:",
                    "AI RECOMMENDATION:",
                    "RECOMMENDATION REASON:",
                ],
            ),

            (
                "CRITICAL POLICY / CONTROL ISSUES:",
                "Critical Policy / Control Issues",
                [
                    "AI RECOMMENDATION:",
                    "RECOMMENDATION REASON:",
                    "REQUIRED ACTIONS BEFORE FINAL DECISION:",
                ],
            ),

            (
                "RECOMMENDATION REASON:",
                "Recommendation Reason",
                [
                    "REQUIRED ACTIONS BEFORE FINAL DECISION:",
                    "HUMAN REVIEW REQUIRED:",
                ],
            ),

            (
                "REQUIRED ACTIONS BEFORE FINAL DECISION:",
                "Required Actions Before Final Decision",
                [
                    "HUMAN REVIEW REQUIRED:",
                ],
            ),
        ]

        rendered_titles = set()

        for (
            section_heading,
            section_title,
            next_headings,
        ) in synthesis_section_definitions:

            if section_title in rendered_titles:
                continue

            section_value = (
                get_synthesis_section(
                    synthesis_result,
                    section_heading,
                    next_headings,
                )
            )

            if not section_value:
                continue

            rendered_titles.add(section_title)

            story.append(
                Paragraph(
                    escape(section_title),
                    subsection_style,
                )
            )

            add_pdf_text(
                story,
                section_value,
                body_style,
            )

        # ----------------------------------------------------
        # HUMAN REVIEW REQUIRED
        # ----------------------------------------------------

        human_review_required = None

        if isinstance(
            synthesis_result,
            dict,
        ):

            human_review_required = (
                synthesis_result.get(
                    "human_review_required"
                )
            )

            if human_review_required is None:

                plain_text_value = (
                    synthesis_result.get("text")
                )

                if plain_text_value:

                    human_review_required = (
                        extract_plain_text_section(
                            plain_text_value,
                            "HUMAN REVIEW REQUIRED:",
                            [],
                        )
                    )

        if human_review_required is None:

            human_review_required = (
                review.get(
                    "human_review_required"
                )
            )

        if human_review_required is not None:

            if isinstance(
                human_review_required,
                str,
            ):

                normalized_review_value = (
                    human_review_required
                    .strip()
                    .upper()
                )

                human_review_required = (
                    normalized_review_value
                    in [
                        "YES",
                        "TRUE",
                        "1",
                    ]
                )

            story.append(
                Paragraph(
                    (
                        "<b>Human Review Required:</b> "
                        f"{'YES' if human_review_required else 'NO'}"
                    ),
                    body_style,
                )
            )

    # ========================================================
    # HUMAN DECISION
    # ========================================================

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

        comments = decision.get("comments")

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
                (
                    "No human decision has "
                    "been recorded for this case."
                ),
                body_style,
            )
        )

    # ========================================================
    # WORKFLOW
    # ========================================================

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
                            step.get("step_name")
                        ),
                        small_style,
                    ),

                    Paragraph(
                        pdf_escape(
                            safe_text(
                                step.get("status")
                            ).upper()
                        ),
                        small_style,
                    ),

                    Paragraph(
                        pdf_escape(
                            step.get("provider")
                        ),
                        small_style,
                    ),

                    Paragraph(
                        pdf_escape(
                            step.get("model")
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
                (
                    "No AI workflow checkpoints "
                    "were recorded."
                ),
                body_style,
            )
        )

    # ========================================================
    # AUDIT TRAIL
    # ========================================================

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
                        f"<b>"
                        f"{pdf_escape(timestamp)} "
                        f"— "
                        f"{pdf_escape(action)}"
                        f"</b>"
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
                Spacer(
                    1,
                    2 * mm,
                )
            )

    else:

        story.append(
            Paragraph(
                "No audit events were recorded.",
                body_style,
            )
        )

    # ========================================================
    # DISCLAIMER
    # ========================================================

    story.append(
        Spacer(
            1,
            5 * mm,
        )
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

    # ========================================================
    # BUILD PDF
    # ========================================================

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
