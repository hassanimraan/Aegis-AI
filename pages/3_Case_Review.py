import streamlit as st

from database.supabase_client import get_supabase
from services.ai_review import run_ai_case_review


st.set_page_config(
    page_title="AI Case Review",
    page_icon="🤖",
    layout="wide"
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
    f"{case.get('title', 'Untitled')} — PKR {case.get('amount', 0):,.0f}":
        case
    for case in cases
}


selected_label = st.selectbox(
    "Select Case",
    list(case_options.keys())
)


case = case_options[selected_label]


st.subheader(case.get("title", "Case"))


col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Department",
        case.get("department", "—")
    )

with col2:
    st.metric(
        "Amount",
        f"PKR {float(case.get('amount', 0)):,.0f}"
    )

with col3:
    st.metric(
        "Status",
        case.get("status", "—")
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
# Run AI review
# ---------------------------------------------------------

if st.button(
    "🚀 Run AI Case Review",
    type="primary",
    use_container_width=True
):

    with st.spinner("Running policy and multi-agent review..."):

        try:

            result = run_ai_case_review(
                case,
                documents
            )

            st.session_state["ai_case_review"] = result
            st.session_state["ai_case_review_id"] = case["id"]

            st.success("AI Case Review completed.")

        except Exception as e:

            st.error(
                f"AI review failed: {str(e)}"
            )


# ---------------------------------------------------------
# Display review
# ---------------------------------------------------------

if (
    st.session_state.get("ai_case_review_id")
    == case["id"]
    and "ai_case_review" in st.session_state
):

    result = st.session_state["ai_case_review"]

    st.divider()

    st.subheader("📋 Evidence Requirements")

    requirements = result["requirements"]

    if requirements:

        for item in requirements:

            if item["status"] == "COMPLETE":
                st.success(
                    f"✅ {item['name']}"
                )

            else:
                st.error(
                    f"❌ {item['name']} — MISSING"
                )

            st.caption(
                item.get("reason", "")
            )

    else:

        st.info(
            "No mandatory evidence requirements were "
            "identified from the retrieved policy evidence."
        )


    # -----------------------------------------------------
    # Evidence Gate
    # -----------------------------------------------------

    gate = result["evidence_gate"]

    st.subheader("🔐 Evidence Gate")

    if gate["complete"]:

        st.success(
            "✅ Evidence Gate PASSED — "
            "all identified mandatory evidence is available."
        )

    else:

        st.error(
            f"🔴 Evidence Gate BLOCKED — "
            f"{gate['missing_count']} mandatory requirement(s) missing."
        )

        for item in gate["missing"]:
            st.write(
                f"• **{item['name']}** — "
                f"{item.get('reason', '')}"
            )


    # -----------------------------------------------------
    # AI assessments
    # -----------------------------------------------------

    st.divider()

    st.subheader("Compliance Assessment")

    st.write(
        result["compliance"]
    )


    st.subheader("Financial Assessment")

    st.write(
        result["financial"]
    )


    st.subheader("Risk Assessment")

    st.write(
        result["risk"]
    )


    st.subheader("Decision Synthesis")

    st.write(
        result["synthesis"]
    )
