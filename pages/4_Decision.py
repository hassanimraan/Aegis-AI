import json
from datetime import datetime, timezone

import streamlit as st

from database.supabase_client import get_supabase
from rag.retriever import search_policies
from services.llm_router import generate_with_fallback


st.set_page_config(
    page_title="Human Decision - AegisAI",
    page_icon="⚖️",
    layout="wide",
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

def parse_timestamp(value):
    """
    Convert a Supabase timestamp into a timezone-aware datetime.
    """

    if not value:
        return None

    try:

        timestamp = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        if timestamp.tzinfo is None:

            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp

    except Exception:

        return None


def load_latest_evidence_change(case_id):
    """
    Load the most recent evidence-change audit event.
    """

    try:

        response = (
            supabase
            .table("audit_logs")
            .select(
                "id, action, details, created_at"
            )
            .eq(
                "case_id",
                case_id
            )
            .eq(
                "action",
                "EVIDENCE_CHANGED"
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(1)
            .execute()
        )

        records = response.data or []

        if records:

            return records[0]

    except Exception:

        pass

    return None


def decision_is_superseded(
    decision,
    evidence_change
):
    """
    A decision is superseded when evidence changed after
    that decision was recorded.
    """

    if not decision or not evidence_change:

        return False

    decision_time = parse_timestamp(
        decision.get("created_at")
    )

    evidence_change_time = parse_timestamp(
        evidence_change.get("created_at")
    )

    if not decision_time or not evidence_change_time:

        return False

    return evidence_change_time > decision_time
# ---------------------------------------------------------
# Page Navigation Helper
# ---------------------------------------------------------

def show_page_navigation(previous_key, next_key):
    st.divider()

    nav_left, nav_right = st.columns(2)

    with nav_left:
        if st.button(
            "← Case Review",
            use_container_width=True,
            key=previous_key,
        ):
            st.switch_page(
                "pages/3_Case_Review.py"
            )

    with nav_right:
        if st.button(
            "Next: Case History →",
            use_container_width=True,
            key=next_key,
        ):
            st.switch_page(
                "pages/5_Case_History.py"
            )


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("⚖️ Human Review & Decision")

st.write(
    "Review the AI assessment, ask grounded questions using "
    "the AegisAI assistant, and make the final human decision."
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

    show_page_navigation(
        "decision_previous_db_error",
        "decision_next_db_error",
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
            st.session_state["user"].id,
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

    show_page_navigation(
        "decision_previous_cases_error",
        "decision_next_cases_error",
    )

    st.stop()


if not cases:
    st.info(
        "No approval cases are available for human review."
    )

    show_page_navigation(
        "decision_previous_no_cases",
        "decision_next_no_cases",
    )

    st.stop()


# ---------------------------------------------------------
# Case Selection
# ---------------------------------------------------------

case_options = {
    (
        f"{case.get('title', 'Untitled')} — "
        f"PKR {float(case.get('amount', 0)):,.0f} "
        f"— Case #{case.get('id')}"
    ): case
    for case in cases
}

selected_label = st.selectbox(
    "Select Approval Case",
    list(case_options.keys()),
)

case = case_options[selected_label]
current_case_id = case["id"]

# ---------------------------------------------------------
# Case Information
# ---------------------------------------------------------

st.subheader("📋 Case Information")

col1, col2, col3 = st.columns(3)

with col1:
    st.write(
        f"**Title:** {case.get('title', '—')}"
    )

with col2:
    st.write(
        f"**Department:** {case.get('department', '—')}"
    )

with col3:
    st.write(
        f"**Amount:** PKR "
        f"{float(case.get('amount', 0)):,.0f}"
    )

st.write(
    f"**Status:** {case.get('status', 'UNKNOWN')}"
)

st.divider()


# ---------------------------------------------------------
# Reset Chat When Case Changes
# ---------------------------------------------------------

if st.session_state.get(
    "decision_chat_case_id"
) != current_case_id:

    st.session_state[
        "decision_chat_case_id"
    ] = current_case_id

    st.session_state[
        "decision_chat_messages"
    ] = []


# ---------------------------------------------------------
# Latest AI Review
# ---------------------------------------------------------

try:
    review_response = (
        supabase
        .table("ai_reviews")
        .select("*")
        .eq(
            "case_id",
            current_case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    reviews = review_response.data or []

except Exception as e:
    st.error(
        f"Unable to load AI review: {e}"
    )

    show_page_navigation(
        "decision_previous_review_error",
        "decision_next_review_error",
    )

    st.stop()


# ---------------------------------------------------------
# No AI Review
# ---------------------------------------------------------

if not reviews:
    st.warning(
        "No completed AI review is available for this case."
    )

    st.info(
        "This case must complete the AI review workflow "
        "before a human final decision can be recorded."
    )

    show_page_navigation(
        "decision_previous_no_review",
        "decision_next_no_review",
    )

    st.stop()


review = reviews[0]


# ---------------------------------------------------------
# Parse Evidence Gate
# ---------------------------------------------------------

gate = review.get("evidence_gate", {})

if isinstance(gate, str):
    try:
        gate = json.loads(gate)
    except Exception:
        gate = {}

if not isinstance(gate, dict):
    gate = {}


# ---------------------------------------------------------
# Parse Requirements
# ---------------------------------------------------------

requirements = review.get(
    "requirements",
    [],
)

if isinstance(requirements, str):
    try:
        requirements = json.loads(requirements)
    except Exception:
        requirements = []

if not isinstance(requirements, list):
    requirements = []


# ---------------------------------------------------------
# AI Assessment
# ---------------------------------------------------------

st.subheader("🤖 AI Assessment")

recommendation = review.get(
    "recommendation",
    "Not available",
)

st.info(
    f"**AI Recommendation:** {recommendation}"
)


with st.expander(
    "View Consolidated AI Assessment",
    expanded=True,
):
    st.write(
        review.get(
            "synthesis",
            "No consolidated assessment available.",
        )
    )


# ---------------------------------------------------------
# Evidence Gate
# ---------------------------------------------------------

st.divider()

st.subheader("🔐 Evidence Gate")

if gate.get("complete", False):

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

    missing = gate.get(
        "missing",
        [],
    )

    if isinstance(missing, list) and missing:

        st.subheader("📋 Missing Evidence")

        for item in missing:

            st.write(
                f"❌ **{item.get('name', 'Requirement')}**"
            )

            reason = item.get("reason")

            if reason:
                st.caption(reason)

    else:

        st.info(
            "The Evidence Gate is incomplete, "
            "but no specific missing requirement "
            "was returned."
        )


# ---------------------------------------------------------
# Load Case Documents
# ---------------------------------------------------------

try:
    documents_response = (
        supabase
        .table("documents")
        .select("*")
        .eq(
            "case_id",
            current_case_id,
        )
        .execute()
    )

    documents = documents_response.data or []

except Exception as e:

    st.error(
        f"Unable to load case documents: {e}"
    )

    documents = []


# ---------------------------------------------------------
# Grounded Review Assistant
# ---------------------------------------------------------

st.divider()

st.subheader("💬 AegisAI Review Assistant")

st.write(
    "Ask questions about the case, supplied documents, "
    "or applicable PEIS policies."
)


# ---------------------------------------------------------
# Display Previous Messages
# ---------------------------------------------------------

for message in st.session_state.get(
    "decision_chat_messages",
    [],
):

    with st.chat_message(
        message["role"]
    ):

        st.write(
            message["content"]
        )


# ---------------------------------------------------------
# Chat Input
# ---------------------------------------------------------

question = st.text_input(
    "Ask a question",
    placeholder=(
        "Why does this case require "
        "three vendor quotations?"
    ),
    key="decision_chat_input",
)

send_question = st.button(
    "Send Question",
    type="primary",
    key="send_decision_question",
)


# ---------------------------------------------------------
# Process Question
# ---------------------------------------------------------

if send_question and question.strip():

    st.session_state[
        "decision_chat_messages"
    ].append(
        {
            "role": "user",
            "content": question.strip(),
        }
    )

    with st.chat_message("user"):
        st.write(question.strip())

    try:

        # -------------------------------------------------
        # Retrieve Policy Evidence
        # -------------------------------------------------

        policy_evidence = search_policies(
            question.strip(),
            top_k=6,
        )

        policy_text = "\n\n".join(
            [
                f"{item.get('policy_id', '')} — "
                f"{item.get('policy_name', '')}\n"
                f"{item.get('section_id', '')} — "
                f"{item.get('section_title', '')}\n"
                f"{item.get('content', '')}"
                for item in policy_evidence
            ]
        )


        # -------------------------------------------------
        # Document Context
        # -------------------------------------------------

        document_text = "\n\n".join(
            [
                f"DOCUMENT: "
                f"{doc.get('document_name', '')}\n"
                f"TYPE: "
                f"{doc.get('document_type', '')}\n"
                f"CONTENT:\n"
                f"{doc.get('extracted_text', '')}"
                for doc in documents
            ]
        )


        # -------------------------------------------------
        # Previous Chat
        # -------------------------------------------------

        chat_history = "\n\n".join(
            [
                f"{message['role'].upper()}: "
                f"{message['content']}"
                for message in st.session_state[
                    "decision_chat_messages"
                ][-6:]
            ]
        )


        # -------------------------------------------------
        # Grounded Prompt
        # -------------------------------------------------

        prompt = f"""
You are the AegisAI Review Assistant.

You help a human reviewer understand an approval case.

Your answers MUST be grounded ONLY in:

1. The supplied case information
2. The supplied case documents
3. The retrieved PEIS policy evidence
4. The completed AI review

Do not invent policies, facts, documents, approvals,
financial reviews, vendor information, or requirements.

If the available evidence is insufficient, clearly say:

"That cannot be determined from the available evidence."

Do not make the final approval decision.

The human reviewer remains responsible for:
Approve / Return / Reject.

==================================================
CASE
==================================================

Title: {case.get("title", "")}

Department: {case.get("department", "")}

Amount: PKR {case.get("amount", "")}

Description:

{case.get("description", "")}


==================================================
SUPPLIED DOCUMENTS
==================================================

{document_text}


==================================================
RETRIEVED POLICY EVIDENCE
==================================================

{policy_text}


==================================================
COMPLETED AI REVIEW
==================================================

{review.get("synthesis", "")}


==================================================
PREVIOUS CONVERSATION
==================================================

{chat_history}


==================================================
USER QUESTION
==================================================

{question.strip()}

Answer clearly and briefly.

When referring to a policy, cite its policy ID
and section ID, for example:

POL-001 P-02

Do not provide a final human decision.
"""


        # -------------------------------------------------
        # LLM Fallback Router
        # -------------------------------------------------

        llm_result = generate_with_fallback(
            prompt
        )

        answer = llm_result.get(
            "text",
            "",
        )

        if not answer:
            raise ValueError(
                "The review assistant returned an empty response."
            )


        # -------------------------------------------------
        # Display Assistant Response
        # -------------------------------------------------

        with st.chat_message("assistant"):
            st.write(answer)


        # -------------------------------------------------
        # Save Assistant Response
        # -------------------------------------------------

        st.session_state[
            "decision_chat_messages"
        ].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )


    except Exception as e:

        st.error(
            f"Assistant failed: {e}"
        )


# ---------------------------------------------------------
# Human Final Decision
# ---------------------------------------------------------

st.divider()

st.subheader("👤 Human Final Decision")

st.warning(
    "The AI recommendation is advisory only. "
    "The final decision must be made by the human reviewer."
)


# ---------------------------------------------------------
# Check Existing Human Decision
# ---------------------------------------------------------

try:

    existing_decision_response = (
        supabase
        .table("decisions")
        .select(
            "id, decision, comments, created_at"
        )
        .eq(
            "case_id",
            current_case_id
        )
        .order(
            "created_at",
            desc=True
        )
        .execute()
    )

    existing_decisions = (
        existing_decision_response.data or []
    )

except Exception as e:

    existing_decisions = []

    st.warning(
        f"Unable to check previous decision: {e}"
    )


# ---------------------------------------------------------
# Load Latest Evidence Change
# ---------------------------------------------------------

latest_evidence_change = (
    load_latest_evidence_change(
        current_case_id
    )
)


# ---------------------------------------------------------
# Determine Whether Existing Decision Is Superseded
# ---------------------------------------------------------

previous_decision = (
    existing_decisions[0]
    if existing_decisions
    else None
)

previous_decision_superseded = (
    decision_is_superseded(
        previous_decision,
        latest_evidence_change
    )
)


# ---------------------------------------------------------
# Existing Final Decision
# ---------------------------------------------------------

if (
    previous_decision
    and not previous_decision_superseded
):

    st.success(
        "✅ Current final decision: "
        f"{previous_decision.get('decision', 'N/A')}"
    )

    st.write(
        "**Decision Date:** "
        f"{previous_decision.get('created_at', 'N/A')}"
    )

    st.write(
        "**Reviewer Comments:** "
        f"{previous_decision.get('comments') or 'None'}"
    )

    st.info(
        "This case currently has an active human final decision."
    )


# ---------------------------------------------------------
# Previous Decision Has Been Superseded
# ---------------------------------------------------------

elif (
    previous_decision
    and previous_decision_superseded
):

    st.warning(
        "⚠️ Previous human decision is SUPERSEDED."
    )

    st.write(
        "**Previous Decision:** "
        f"{previous_decision.get('decision', 'N/A')}"
    )

    st.write(
        "**Previous Decision Date:** "
        f"{previous_decision.get('created_at', 'N/A')}"
    )

    st.write(
        "**Previous Reviewer Comments:** "
        f"{previous_decision.get('comments') or 'None'}"
    )

    st.info(
        "Case evidence changed after the previous human "
        "decision. The previous decision remains in the "
        "audit/history record but no longer applies to the "
        "current evidence."
    )

    st.warning(
        "A new AI review must be completed before a new "
        "human decision can be submitted."
    )


# ---------------------------------------------------------
# New Human Decision
# ---------------------------------------------------------

if (
    not previous_decision
    or previous_decision_superseded
):

    if not gate.get(
        "complete",
        False
    ):

        st.error(
            "🔴 FINAL DECISION LOCKED"
        )

        if previous_decision_superseded:

            st.warning(
                "The previous decision was superseded because "
                "case evidence changed. The updated evidence "
                "must pass the AI Evidence Gate before a new "
                "human decision can be made."
            )

        else:

            st.warning(
                "Mandatory policy-required evidence is incomplete. "
                "Please upload the missing evidence and run AI "
                "Case Review again before making the final decision."
            )

        st.subheader(
            "📋 Missing Evidence"
        )

        missing = gate.get(
            "missing",
            []
        )

        if (
            isinstance(missing, list)
            and missing
        ):

            for item in missing:

                st.write(
                    f"❌ **"
                    f"{item.get('name', 'Requirement')}"
                    f"**"
                )

                if item.get("reason"):

                    st.caption(
                        item["reason"]
                    )

        else:

            st.info(
                "The Evidence Gate is incomplete, "
                "but no specific missing requirement "
                "was returned."
            )

    else:

        st.success(
            "🟢 Evidence Gate passed. "
            "Human decision controls are available."
        )

        decision = st.radio(
            "Select Decision",
            [
                "Approve",
                "Return",
                "Reject",
            ],
            horizontal=True,
            key="human_decision_choice",
        )

        comments = st.text_area(
            "Reviewer Comments",
            placeholder=(
                "Enter your decision comments..."
            ),
            key="human_decision_comments",
        )

        if decision in [
            "Return",
            "Reject",
        ] and not comments.strip():

            st.info(
                "Reviewer comments are required for "
                "Return or Reject."
            )

        # -------------------------------------------------
        # Submit Decision
        # -------------------------------------------------

        if st.button(
            "Submit Final Decision",
            type="primary",
            use_container_width=True,
            key="submit_human_decision",
        ):

            if decision in [
                "Return",
                "Reject",
            ] and not comments.strip():

                st.error(
                    "Please enter reviewer comments."
                )

            else:

                try:

                    # -------------------------------------
                    # Save New Human Decision
                    # -------------------------------------

                    supabase.table(
                        "decisions"
                    ).insert(
                        {
                            "case_id": current_case_id,
                            "reviewer_id": (
                                st.session_state[
                                    "user"
                                ].id
                            ),
                            "decision": decision,
                            "comments": comments.strip(),
                        }
                    ).execute()

                    # -------------------------------------
                    # Update Case Status
                    # -------------------------------------

                    status_map = {
                        "Approve": "APPROVED",
                        "Return": "RETURNED",
                        "Reject": "REJECTED",
                    }

                    new_status = status_map[
                        decision
                    ]

                    supabase.table(
                        "cases"
                    ).update(
                        {
                            "status": new_status,
                        }
                    ).eq(
                        "id",
                        current_case_id,
                    ).execute()

                    # -------------------------------------
                    # Audit Log
                    # -------------------------------------

                    supabase.table(
                        "audit_logs"
                    ).insert(
                        {
                            "case_id": current_case_id,
                            "user_id": (
                                st.session_state[
                                    "user"
                                ].id
                            ),
                            "action": (
                                "HUMAN_DECISION_"
                                f"{decision.upper()}"
                            ),
                            "details": (
                                "Human reviewer selected "
                                f"{decision}. "
                                "Comments: "
                                f"{comments.strip() or 'None'}"
                            ),
                        }
                    ).execute()

                    # -------------------------------------
                    # Confirmation
                    # -------------------------------------

                    st.success(
                        "✅ Human decision saved successfully: "
                        f"{decision}"
                    )

                    st.info(
                        f"Case status updated to: {new_status}"
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "Unable to save the human decision: "
                        f"{e}"
                    )
# ---------------------------------------------------------
# PAGE NAVIGATION
# ---------------------------------------------------------

show_page_navigation(
    "decision_previous",
    "decision_next",
)
