import streamlit as st

from database.supabase_client import get_supabase


st.title("📊 AegisAI Dashboard")


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------
if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning("Please log in to continue.")
    st.stop()


supabase = get_supabase()
user_id = st.session_state["user"].id


# ---------------------------------------------------------
# Load user's cases
# ---------------------------------------------------------
response = (
    supabase.table("cases")
    .select("*")
    .eq("user_id", user_id)
    .order("created_at", desc=True)
    .execute()
)

cases = response.data or []


# ---------------------------------------------------------
# Calculate statistics
# ---------------------------------------------------------
total_cases = len(cases)

pending_cases = sum(
    1
    for case in cases
    if str(case.get("status", "")).upper()
    in ["DRAFT", "PENDING", "UNDER_REVIEW"]
)

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


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Cases", total_cases)

with col2:
    st.metric("Pending", pending_cases)

with col3:
    st.metric("Approved", approved_cases)

with col4:
    st.metric("Returned", returned_cases)


# ---------------------------------------------------------
# Recent Cases
# ---------------------------------------------------------
st.divider()
st.subheader("📋 Recent Cases")


if not cases:
    st.info("No approval cases found.")
    st.stop()


for case in cases:

    status = str(
        case.get("status", "UNKNOWN")
    ).upper()

    title = case.get(
        "title",
        "Untitled Case"
    )

    department = case.get(
        "department",
        "N/A"
    )

    amount = case.get(
        "amount",
        0
    )

    try:
        amount_display = f"PKR {float(amount):,.0f}"
    except (TypeError, ValueError):
        amount_display = "PKR N/A"

    created_at = case.get(
        "created_at",
        "N/A"
    )

    with st.expander(
        f"{title} — {status}"
    ):
        st.write(
            f"**Department:** {department}"
        )

        st.write(
            f"**Amount:** {amount_display}"
        )

        st.write(
            f"**Status:** {status}"
        )

        st.write(
            f"**Created:** {created_at}"
        )


st.divider()

st.caption(
    "AegisAI Dashboard — AI recommendations are advisory; "
    "human decisions are authoritative."
)
