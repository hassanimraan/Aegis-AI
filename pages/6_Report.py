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
    layout="wide"
)


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning(
        "Please log in from the main AegisAI page."
    )
    st.stop()


# ---------------------------------------------------------
# Supabase
# ---------------------------------------------------------

try:
    supabase = get_supabase()

except Exception as e:
    st.error(
        f"Unable to connect to Supabase: {e}"
    )
    st.stop()


st.title("📄 Approval Report")

st.write(
    "View and download the complete AI-assisted approval report."
)

st.divider()


# ---------------------------------------------------------
# Load Cases
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Select Case
# ---------------------------------------------------------

def format_amount(value):
    try:
        return f"PKR {float(value):,.0f}"
    except (TypeError, ValueError):
        return "PKR N/A"


case_options = {}

for case_item in cases:

    title = case_item.get(
        "title",
        "Untitled"
    )

    amount_display = format_amount(
        case_item.get("amount", 0)
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


# ---------------------------------------------------------
# Load AI Review
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Load Human Decision
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Load Audit Logs
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Case Information
# ---------------------------------------------------------

st.subheader("📌 Case Information")

col1, col2, col3 = st.columns(3)

with col1:
    st.write(
        f"**Case:** "
        f"{case.get('title', 'N/A')}"
    )

    st.write(
        f"**Department:** "
        f"{case.get('department', 'N/A')}"
    )

with col2:
    st.write(
        f"**Amount:** "
        f"{format_amount(case.get('amount', 0))}"
    )

    st.write(
        f"**Status:** "
        f"{case.get('status', 'N/A')}"
    )

with col3:
    st.write(
        f"**Created:** "
        f"{case.get('created_at', 'N/A')}"
    )


st.divider()


# ---------------------------------------------------------
# AI Assessment
# ---------------------------------------------------------

st.subheader("🤖 AI Assessment")

if review:

    st.info(
        f"**AI Recommendation:** "
        f"{review.get('recommendation', 'N/A')}"
    )

    if review.get("synthesis"):

        st.write("### Decision Synthesis")

        st.write(
            review.get("synthesis")
        )

else:

    st.warning(
        "No AI review is available for this case."
    )


st.divider()


# ---------------------------------------------------------
# Human Decision
# ---------------------------------------------------------

st.subheader("👤 Human Decision")

if decision:

    col1, col2 = st.columns(2)

    with col1:
        st.success(
            f"**Final Decision:** "
            f"{decision.get('decision', 'N/A')}"
        )

    with col2:
        st.write(
            f"**Decision Date:** "
            f"{decision.get('created_at', 'N/A')}"
        )

    st.write(
        f"**Reviewer Comments:** "
        f"{decision.get('comments') or 'None'}"
    )

else:

    st.warning(
        "No human decision has been recorded."
    )


st.divider()


# ---------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------

st.subheader("📝 Audit Trail")

if audit_logs:

    for log in audit_logs:

        st.write(
            f"**{log.get('created_at', 'N/A')}** — "
            f"{log.get('action', 'N/A')}"
        )

        if log.get("details"):

            st.caption(
                log.get("details")
            )

else:

    st.info(
        "No audit records available."
    )


st.divider()


# ---------------------------------------------------------
# PDF Helpers
# ---------------------------------------------------------

def pdf_text(value):
    """
    Safely convert arbitrary text to ReportLab-compatible
    escaped HTML/XML text.
    """

    if value is None:
        return ""

    return html.escape(
        str(value)
    ).replace(
        "\n",
        "<br/>"
    )


# ---------------------------------------------------------
# PDF Report Generator
# ---------------------------------------------------------

def generate_pdf():

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    story = []

    story.append(
        Paragraph(
            "AegisAI — Approval & Compliance Report",
            title_style
        )
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # Case Information
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Case Information</b>",
            styles["Heading2"]
        )
    )

    case_data = [
        [
            "Case",
            pdf_text(case.get("title", "N/A"))
        ],
        [
            "Department",
            pdf_text(case.get("department", "N/A"))
        ],
        [
            "Amount",
            pdf_text(
                format_amount(
                    case.get("amount", 0)
                )
            )
        ],
        [
            "Status",
            pdf_text(
                case.get("status", "N/A")
            )
        ],
        [
            "Created",
            pdf_text(
                case.get("created_at", "N/A")
            )
        ],
    ]

    table = Table(
        case_data,
        colWidths=[130, 350]
    )

    table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.lightgrey
            ),
            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "Helvetica-Bold"
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    story.append(table)

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # AI Recommendation
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>AI Assessment</b>",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            (
                "<b>AI Recommendation:</b> "
                f"{pdf_text(review.get('recommendation', 'N/A'))}"
            ),
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 10)
    )

    synthesis = review.get(
        "synthesis",
        "No AI synthesis available."
    )

    story.append(
        Paragraph(
            pdf_text(synthesis),
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # Human Decision
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Human Decision</b>",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Final Decision:</b> "
                f"{pdf_text(decision.get('decision', 'N/A'))}"
            ),
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Comments:</b> "
                f"{pdf_text(decision.get('comments') or 'None')}"
            ),
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )


    # -----------------------------------------------------
    # Audit Trail
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "<b>Audit Trail</b>",
            styles["Heading2"]
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
                    styles["BodyText"]
                )
            )

            story.append(
                Spacer(1, 5)
            )

    else:

        story.append(
            Paragraph(
                "No audit records available.",
                styles["BodyText"]
            )
        )


    story.append(
        Spacer(1, 20)
    )

    story.append(
        Paragraph(
            (
                "AegisAI — AI recommendations are advisory. "
                "Human decisions are authoritative."
            ),
            styles["Italic"]
        )
    )

    document.build(
        story
    )

    buffer.seek(0)

    return buffer


# ---------------------------------------------------------
# Download PDF
# ---------------------------------------------------------

st.subheader("📥 Download Report")

pdf_file = generate_pdf()

st.download_button(
    label="Download PDF Report",
    data=pdf_file,
    file_name="AegisAI_Approval_Report.pdf",
    mime="application/pdf",
    type="primary",
    use_container_width=True
)
