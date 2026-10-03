import streamlit as st

from database.supabase_client import get_supabase
from services.ai_review import run_ai_case_review


st.set_page_config(
    page_title="AI Case Review",
    page_icon="🤖",
    layout="wide",
)


if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()


supabase = get_supabase()
user = st.session_state["user"]


st.title("🤖 AI Case Review")
st.caption(
    "Policy-driven AI assessment with evidence validation."
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

STEP_DEFINITIONS = [
    ("RAG", "1. RAG Policy Retrieval"),
    ("COMPLIANCE", "2. Compliance Agent"),
    ("FINANCIAL", "3. Financial Agent"),
    ("RISK", "4. Risk Agent"),
    ("SYNTHESIS", "5. Decision Synthesizer"),
    ("EVIDENCE", "6. Evidence Gate"),
]


def get_review_steps(case_id):
    response = (
        supabase
        .table("ai_review_steps")
        .select("*")
        .eq("case_id", case_id)
        .order("step_order")
        .execute()
    )

    return response.data or []


def display_step_status(case_id):
    steps = get_review_steps(case_id)

    status_map = {
        step.get("step_name"): step
        for step in steps
    }

    st.subheader("🔄 AI Review Workflow")

    completed_count = 0

    for step_name, label in STEP_DEFINITIONS:
        step = status_map.get(step_name)

        if not step:
            st.info(f"⏳ {label} — PENDING")
            continue

        status = step.get("status", "PENDING")

        if status == "COMPLETED":
            completed_count += 1
            st.success(f"✅ {label} — COMPLETED")

            provider = step.get("provider")
            model = step.get("model")

            if provider or model:
                st.caption(
                    f"Provider: {provider or '—'} | "
                    f"Model: {model or '—'}"
                )

        elif status == "RUNNING":
            st.warning(f"🔄 {label} — RUNNING")

        elif status == "FAILED":
            st.error(f"❌ {label} — FAILED")

            error = step.get("error")

            if error:
                st.caption(str(error))

        else:
            st.info(f"⏳ {label} — {status}")

    progress = completed_count / len(STEP_DEFINITIONS)

    st.progress(
        progress,
        text=f"{completed_count}/{len(STEP_DEFINITIONS)} workflow steps completed",
    )


def get_result_text(value):
    if isinstance(value, dict):
        return value.get("text", "")

    if value is None:
        return ""

    return str(value)


# ---------------------------------------------------------
# Load cases
# ---------------------------------------------------------

response = (
    supabase
    .table("cases")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", desc=True)
    .execute()
)

cases = response.data or []


if not cases:
    st.info("No cases available.")
    st.stop()


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


# ---------------------------------------------------------
# Case summary
# ---------------------------------------------------------

st.subheader(case.get("title", "Case"))


col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "Department",
        case.get("department", "—"),
    )


with col2:
    st.metric(
        "Amount",
        f"PKR {float(case.get('amount', 0)):,.0f}",
    )


with col3:
    st.metric(
        "Status",
        case.get("status", "—"),
    )


# ---------------------------------------------------------
# Documents
# ---------------------------------------------------------

doc_response = (
    supabase
    .table("documents")
    .select("*")
    .eq("case_id", case["id"])
    .execute()
)

documents = doc_response.data or []


st.subheader("Available Evidence")


if documents:
    for doc in documents:
        st.write(
            f"• **{doc.get('document_type', 'Other')}** — "
            f"{doc.get('document_name', 'Unnamed document')}"
        )
else:
    st.warning("No documents uploaded.")


# ---------------------------------------------------------
# Persistent workflow status
# ---------------------------------------------------------

st.divider()

display_step_status(case["id"])


# ---------------------------------------------------------
# Run / Resume AI Review
# ---------------------------------------------------------

st.divider()

st.subheader("AI Review Control")

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

            st.session_state["ai_case_review"] = result
            st.session_state["ai_case_review_id"] = case["id"]

            st.success(
                "AI Case Review completed successfully."
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"AI review failed: {str(e)}"
            )

            st.warning(
                "Completed workflow steps have been saved. "
                "Use Run / Resume to continue from the "
                "incomplete step."
            )

            st.rerun()


# ---------------------------------------------------------
# Display review
# ---------------------------------------------------------

if (
    st.session_state.get("ai_case_review_id")
    == case["id"]
    and "ai_case_review" in st.session_state
):

    result = st.session_state["ai_case_review"]


    # -----------------------------------------------------
    # Evidence Requirements
    # -----------------------------------------------------

    st.divider()

    st.subheader("📋 Evidence Requirements")

    requirements = result.get("requirements", [])


    if requirements:

        for item in requirements:

            name = item.get(
                "name",
                "Unnamed requirement",
            )

            status = item.get(
                "status",
                "MISSING",
            )

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

    gate = result.get(
        "evidence_gate",
        {},
    )

    st.subheader("🔐 Evidence Gate")


    if gate.get("complete"):

        st.success(
            "✅ Evidence Gate PASSED — "
            "all identified mandatory evidence is available."
        )

    else:

        missing_count = gate.get(
            "missing_count",
            0,
        )

        st.error(
            f"🔴 Evidence Gate BLOCKED — "
            f"{missing_count} mandatory requirement(s) missing."
        )

        for item in gate.get("missing", []):

            st.write(
                f"• **{item.get('name', 'Requirement')}** — "
                f"{item.get('reason', '')}"
            )


    # -----------------------------------------------------
    # AI Assessments
    # -----------------------------------------------------

    st.divider()

    st.subheader("Compliance Assessment")

    compliance_text = get_result_text(
        result.get("compliance")
    )

    if compliance_text:
        st.write(compliance_text)
    else:
        st.info("Compliance assessment not available.")


    st.subheader("Financial Assessment")

    financial_text = get_result_text(
        result.get("financial")
    )

    if financial_text:
        st.write(financial_text)
    else:
        st.info("Financial assessment not available.")


    st.subheader("Risk Assessment")

    risk_text = get_result_text(
        result.get("risk")
    )

    if risk_text:
        st.write(risk_text)
    else:
        st.info("Risk assessment not available.")


    st.subheader("Decision Synthesis")

    synthesis_text = get_result_text(
        result.get("synthesis")
    )

    if synthesis_text:
        st.write(synthesis_text)
    else:
        st.info("Decision synthesis not available.")


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
