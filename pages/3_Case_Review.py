import json

import streamlit as st

from database.supabase_client import get_supabase
from services.ai_review import run_ai_case_review


st.set_page_config(
    page_title="AI Case Review",
    page_icon="🤖",
    layout="wide",
)


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning("Please log in first.")
    st.stop()


# ---------------------------------------------------------
# Supabase
# ---------------------------------------------------------

try:
    supabase = get_supabase()
except Exception as e:
    st.error(f"Unable to connect to Supabase: {e}")
    st.stop()


user = st.session_state["user"]


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("🤖 AI Case Review")

st.caption(
    "Policy-driven AI assessment with evidence validation."
)


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

STEP_DEFINITIONS = [
    ("RAG", "1. RAG Policy Retrieval"),
    ("COMPLIANCE", "2. Compliance Agent"),
    ("FINANCIAL", "3. Financial Agent"),
    ("RISK", "4. Risk Agent"),
    ("SYNTHESIS", "5. Decision Synthesizer"),
    ("EVIDENCE", "6. Evidence Gate"),
]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_case_id(case):
    """
    Normalize the Supabase case ID to an integer.
    """

    try:
        return int(case["id"])
    except Exception:
        return case["id"]


def get_review_steps(case_id):
    """
    Load the persisted AI workflow checkpoints directly
    from Supabase.
    """

    normalized_case_id = get_case_id(
        {"id": case_id}
    )

    response = (
        supabase
        .table("ai_review_steps")
        .select(
            "id, case_id, step_name, step_order, "
            "status, provider, model, result, error, "
            "started_at, completed_at"
        )
        .eq(
            "case_id",
            normalized_case_id,
        )
        .order(
            "step_order",
            desc=False,
        )
        .execute()
    )

    return response.data or []


def get_latest_ai_review(case_id):
    """
    Load the latest persisted AI review for the case.
    """

    normalized_case_id = get_case_id(
        {"id": case_id}
    )

    response = (
        supabase
        .table("ai_reviews")
        .select("*")
        .eq(
            "case_id",
            normalized_case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    reviews = response.data or []

    if reviews:
        return reviews[0]

    return None


def parse_json_value(value, default):
    """
    Convert JSONB/string JSON values into Python objects.
    """

    if value is None:
        return default

    if isinstance(value, type(default)):
        return value

    if isinstance(value, str):

        try:
            parsed = json.loads(value)

            if isinstance(parsed, type(default)):
                return parsed

        except Exception:
            pass

    return default


def get_result_text(value):
    """
    Extract displayable text from an AI result.
    """

    if isinstance(value, dict):
        return value.get("text", "")

    if value is None:
        return ""

    return str(value)


def display_step_status(case_id):
    """
    Display the persisted AI review workflow state.

    The workflow status is always read from ai_review_steps.
    It does not depend on Streamlit session state.
    """

    try:

        steps = get_review_steps(case_id)

    except Exception as e:

        st.error(
            "Unable to load AI review workflow checkpoints: "
            f"{e}"
        )

        return 0, 0

    status_map = {
        str(step.get("step_name", "")).upper(): step
        for step in steps
    }

    st.subheader("🔄 AI Review Workflow")

    completed_count = 0

    for step_name, label in STEP_DEFINITIONS:

        normalized_step_name = step_name.upper()

        step = status_map.get(
            normalized_step_name
        )

        if not step:

            st.info(
                f"⏳ {label} — PENDING"
            )

            continue

        status = str(
            step.get(
                "status",
                "PENDING",
            )
        ).upper()

        if status == "COMPLETED":

            completed_count += 1

            st.success(
                f"✅ {label} — COMPLETED"
            )

            provider = step.get("provider")
            model = step.get("model")

            if provider or model:

                st.caption(
                    f"Provider: {provider or '—'} | "
                    f"Model: {model or '—'}"
                )

        elif status == "RUNNING":

            st.warning(
                f"🔄 {label} — RUNNING"
            )

        elif status == "FAILED":

            st.error(
                f"❌ {label} — FAILED"
            )

            error = step.get("error")

            if error:
                st.caption(str(error))

        else:

            st.info(
                f"⏳ {label} — {status}"
            )

    total_steps = len(STEP_DEFINITIONS)

    progress = (
        completed_count / total_steps
        if total_steps
        else 0
    )

    st.progress(
        progress,
        text=(
            f"{completed_count}/"
            f"{total_steps} workflow steps completed"
        ),
    )

    return completed_count, total_steps


def display_review_results(review):
    """
    Display the persisted AI review results.
    """

    if not review:
        return

    requirements = parse_json_value(
        review.get("requirements"),
        [],
    )

    evidence_gate = parse_json_value(
        review.get("evidence_gate"),
        {},
    )

    # -----------------------------------------------------
    # Evidence Requirements
    # -----------------------------------------------------

    st.divider()

    st.subheader("📋 Evidence Requirements")

    if requirements:

        for item in requirements:

            name = item.get(
                "name",
                "Unnamed requirement",
            )

            status = str(
                item.get(
                    "status",
                    "MISSING",
                )
            ).upper()

            reason = item.get(
                "reason",
                "",
            )

            if status == "COMPLETE":

                st.success(
                    f"✅ {name}"
                )

            else:

                st.error(
                    f"❌ {name} — MISSING"
                )

            if reason:
                st.caption(reason)

    else:

        st.info(
            "No mandatory evidence requirements were "
            "identified from the retrieved policy evidence."
        )

    # -----------------------------------------------------
    # Evidence Gate
    # -----------------------------------------------------

    st.subheader("🔐 Evidence Gate")

    if evidence_gate.get(
        "complete",
        False,
    ):

        st.success(
            "✅ Evidence Gate PASSED — "
            "all identified mandatory evidence is available."
        )

    else:

        missing_count = evidence_gate.get(
            "missing_count",
            0,
        )

        st.error(
            "🔴 Evidence Gate BLOCKED — "
            f"{missing_count} mandatory requirement(s) missing."
        )

        missing = evidence_gate.get(
            "missing",
            [],
        )

        if isinstance(missing, list):

            for item in missing:

                st.write(
                    f"• **"
                    f"{item.get('name', 'Requirement')}"
                    f"** — "
                    f"{item.get('reason', '')}"
                )

    # -----------------------------------------------------
    # AI Assessments
    # -----------------------------------------------------

    st.divider()

    st.subheader("Compliance Assessment")

    compliance_text = get_result_text(
        review.get("compliance_result")
        or review.get("compliance")
    )

    if compliance_text:
        st.write(compliance_text)
    else:
        st.info(
            "Compliance assessment not available."
        )

    st.subheader("Financial Assessment")

    financial_text = get_result_text(
        review.get("financial_result")
        or review.get("financial")
    )

    if financial_text:
        st.write(financial_text)
    else:
        st.info(
            "Financial assessment not available."
        )

    st.subheader("Risk Assessment")

    risk_text = get_result_text(
        review.get("risk_result")
        or review.get("risk")
    )

    if risk_text:
        st.write(risk_text)
    else:
        st.info(
            "Risk assessment not available."
        )

    st.subheader("Decision Synthesis")

    synthesis_text = get_result_text(
        review.get("synthesis")
    )

    if synthesis_text:
        st.write(synthesis_text)
    else:
        st.info(
            "Decision synthesis not available."
        )

    # -----------------------------------------------------
    # Recommendation
    # -----------------------------------------------------

    recommendation = review.get(
        "recommendation"
    )

    if recommendation:

        st.subheader("🤖 AI Recommendation")

        st.info(
            str(recommendation)
        )


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
            user.id,
        )
        .order(
            "created_at",
            desc=True,
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
        "No cases available."
    )

    st.stop()


# ---------------------------------------------------------
# Case Selection
# ---------------------------------------------------------

case_options = {
    f"{case.get('title', 'Untitled')} — "
    f"PKR {float(case.get('amount', 0)):,.0f}":
        case
    for case in cases
}


selected_label = st.selectbox(
    "Select Case",
    list(case_options.keys()),
)


case = case_options[selected_label]

current_case_id = get_case_id(case)


# ---------------------------------------------------------
# Case Summary
# ---------------------------------------------------------

st.subheader(
    case.get(
        "title",
        "Case",
    )
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Department",
        case.get(
            "department",
            "—",
        ),
    )


with col2:

    st.metric(
        "Amount",
        (
            f"PKR "
            f"{float(case.get('amount', 0)):,.0f}"
        ),
    )


with col3:

    st.metric(
        "Status",
        case.get(
            "status",
            "—",
        ),
    )


# ---------------------------------------------------------
# Documents
# ---------------------------------------------------------

try:

    doc_response = (
        supabase
        .table("documents")
        .select("*")
        .eq(
            "case_id",
            current_case_id,
        )
        .execute()
    )

    documents = doc_response.data or []

except Exception as e:

    st.error(
        f"Unable to load case documents: {e}"
    )

    documents = []


st.subheader(
    "Available Evidence"
)


if documents:

    for doc in documents:

        st.write(
            f"• **"
            f"{doc.get('document_type', 'Other')}"
            f"** — "
            f"{doc.get('document_name', 'Unnamed document')}"
        )

else:

    st.warning(
        "No documents uploaded."
    )


# ---------------------------------------------------------
# Persistent Workflow Status
# ---------------------------------------------------------

st.divider()

completed_count, total_steps = display_step_status(
    current_case_id
)


# ---------------------------------------------------------
# Persisted AI Review
# ---------------------------------------------------------

try:

    persisted_review = get_latest_ai_review(
        current_case_id
    )

except Exception as e:

    persisted_review = None

    st.error(
        "Unable to load the persisted AI review: "
        f"{e}"
    )


# ---------------------------------------------------------
# Run / Resume AI Review
# ---------------------------------------------------------

st.divider()

st.subheader(
    "AI Review Control"
)

st.caption(
    "Run the review or resume it from the last incomplete "
    "workflow step."
)


if st.button(
    "🚀 Run / Resume AI Review",
    type="primary",
    use_container_width=True,
    key="run_resume_ai_review",
):

    with st.spinner(
        "Running policy and multi-agent review..."
    ):

        try:

            result = run_ai_case_review(
                case,
                documents,
            )

            st.session_state[
                "ai_case_review"
            ] = result

            st.session_state[
                "ai_case_review_id"
            ] = current_case_id

            st.success(
                "AI Case Review completed successfully."
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"AI review failed: {e}"
            )

            st.warning(
                "Completed workflow steps have been saved. "
                "Use Run / Resume to continue from the "
                "incomplete step."
            )


# ---------------------------------------------------------
# Determine Review To Display
# ---------------------------------------------------------

session_review = None

if (
    st.session_state.get(
        "ai_case_review_id"
    )
    == current_case_id
):

    session_review = st.session_state.get(
        "ai_case_review"
    )


review_to_display = (
    session_review
    if session_review
    else persisted_review
)


# ---------------------------------------------------------
# Display Persisted / Current Review
# ---------------------------------------------------------

if review_to_display:

    display_review_results(
        review_to_display
    )

else:

    st.info(
        "No completed AI review is available for this case. "
        "Run the AI Review to begin the assessment."
    )


# ---------------------------------------------------------
# PAGE NAVIGATION
# ---------------------------------------------------------

st.divider()

nav_left, nav_right = st.columns(2)


with nav_left:

    if st.button(
        "← Create Case",
        use_container_width=True,
        key="case_review_previous",
    ):

        st.switch_page(
            "pages/2_Create_Case.py"
        )


with nav_right:

    if st.button(
        "Next: Decision →",
        use_container_width=True,
        key="case_review_next",
    ):

        st.switch_page(
            "pages/4_Decision.py"
        )
