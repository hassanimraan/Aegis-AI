import streamlit as st

from database.supabase_client import get_supabase


st.set_page_config(
    page_title="Case History - AegisAI",
    page_icon="📚",
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


st.title("📚 Case History")

st.write(
    "Review previous approval cases, AI recommendations, "
    "human decisions, and audit information."
)

st.divider()


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
        f"Unable to load case history: {e}"
    )

    st.stop()


# ---------------------------------------------------------
# No Cases
# ---------------------------------------------------------

if not cases:

    st.info(
        "No approval cases have been created yet."
    )

    st.stop()


# ---------------------------------------------------------
# Case Summary
# ---------------------------------------------------------

st.subheader("📊 Case Summary")

total_cases = len(cases)

approved_cases = sum(
    1
    for case in cases
    if str(case.get("status", "")).upper() == "APPROVED"
)

returned_cases = sum(
    1
    for case in cases
    if str(case.get("status", "")).upper() == "RETURNED"
)

rejected_cases = sum(
    1
    for case in cases
    if str(case.get("status", "")).upper() == "REJECTED"
)

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Total Cases",
        total_cases
    )

with col2:

    st.metric(
        "Approved",
        approved_cases
    )

with col3:

    st.metric(
        "Returned",
        returned_cases
    )

with col4:

    st.metric(
        "Rejected",
        rejected_cases
    )


st.divider()


# ---------------------------------------------------------
# Case History
# ---------------------------------------------------------

st.subheader("🗂️ Approval Cases")

for case in cases:

    case_id = case["id"]

    status = str(
        case.get("status", "N/A")
    ).upper()

    amount = case.get(
        "amount",
        0
    )

    try:

        amount_display = f"PKR {float(amount):,.0f}"

    except (TypeError, ValueError):

        amount_display = "PKR N/A"


    # -----------------------------------------------------
    # Load Latest AI Review
    # -----------------------------------------------------

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


    review = reviews[0] if reviews else {}


    # -----------------------------------------------------
    # Load Latest Human Decision
    # -----------------------------------------------------

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


    human_decision = (
        decisions[0]
        if decisions
        else {}
    )


    # -----------------------------------------------------
    # Case Header
    # -----------------------------------------------------

    with st.expander(
        f"{case.get('title', 'Untitled Case')} "
        f"— {amount_display}",
        expanded=False
    ):

        col1, col2, col3 = st.columns(3)

        with col1:

            st.write(
                f"**Department:** "
                f"{case.get('department', 'N/A')}"
            )

        with col2:

            st.write(
                f"**Status:** "
                f"{status}"
            )

        with col3:

            st.write(
                f"**Created:** "
                f"{case.get('created_at', 'N/A')}"
            )


        st.divider()


        # -------------------------------------------------
        # AI Recommendation
        # -------------------------------------------------

        st.write("### 🤖 AI Assessment")

        ai_recommendation = review.get(
            "recommendation",
            "No AI review available"
        )

        st.info(
            f"**AI Recommendation:** "
            f"{ai_recommendation}"
        )


        # -------------------------------------------------
        # Human Decision
        # -------------------------------------------------

        st.write("### 👤 Human Decision")

        if human_decision:

            st.success(
                f"**Decision:** "
                f"{human_decision.get('decision', 'N/A')}"
            )

            st.write(
                f"**Decision Date:** "
                f"{human_decision.get('created_at', 'N/A')}"
            )

            st.write(
                f"**Reviewer Comments:** "
                f"{human_decision.get('comments') or 'None'}"
            )

        else:

            st.warning(
                "No human decision has been recorded."
            )


        # -------------------------------------------------
        # AI Assessment Details
        # -------------------------------------------------

        if review:

            with st.expander(
                "View AI Assessment Details"
            ):

                st.write(
                    review.get(
                        "synthesis",
                        "No synthesis available."
                    )
                )


        # -------------------------------------------------
        # Case Description
        # -------------------------------------------------

        with st.expander(
            "View Case Description"
        ):

            st.write(
                case.get(
                    "description",
                    "No description available."
                )
            )


st.divider()

st.caption(
    "AegisAI Case History — Human decisions are authoritative "
    "and AI recommendations are advisory."
)
