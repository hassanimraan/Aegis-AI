import streamlit as st
import json

from database.supabase_client import get_supabase
from rag.retriever import search_policies
from config.settings import get_gemini_api_key

from google import genai


MODEL = "gemini-3.6-flash"


st.set_page_config(
    page_title="Human Decision - AegisAI",
    page_icon="⚖️",
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


st.title("⚖️ Human Review & Decision")

st.write(
    "Review the AI assessment, ask grounded questions using the "
    "AegisAI assistant, and make the final human decision."
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
        f"Unable to load cases: {e}"
    )

    st.stop()


if not cases:

    st.info(
        "No approval cases are available for human review."
    )

    st.stop()


case_options = {
    f"{case['title']} — PKR {float(case['amount']):,.0f}": case
    for case in cases
}


selected_label = st.selectbox(
    "Select Approval Case",
    list(case_options.keys())
)

case = case_options[selected_label]


# ---------------------------------------------------------
# Case Information
# ---------------------------------------------------------

st.subheader("📋 Case Information")

col1, col2, col3 = st.columns(3)

with col1:

    st.write(
        f"**Title:** {case['title']}"
    )

with col2:

    st.write(
        f"**Department:** {case['department']}"
    )

with col3:

    st.write(
        f"**Amount:** PKR {float(case['amount']):,.0f}"
    )


st.write(
    f"**Status:** {case.get('status', 'UNKNOWN')}"
)

st.divider()


# ---------------------------------------------------------
# Reset Chat When Case Changes
# ---------------------------------------------------------

current_case_id = case["id"]

if st.session_state.get(
    "decision_chat_case_id"
) != current_case_id:

    st.session_state["decision_chat_case_id"] = current_case_id

    st.session_state["decision_chat_messages"] = []


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
            current_case_id
        )
        .order(
            "created_at",
            desc=True
        )
        .limit(1)
        .execute()
    )

    reviews = review_response.data or []

    if reviews:

        latest_review = reviews[0]

        st.session_state["ai_case_review_db"] = latest_review

except Exception as e:

    st.error(
        f"Unable to load AI review: {e}"
    )

    st.stop()


if not reviews:

    st.warning(
        "No completed AI review is available for this case."
    )

    st.info(
        "This case must complete the AI review workflow "
        "before a human final decision can be recorded."
    )

    st.stop()


review = reviews[0]


# ---------------------------------------------------------
# AI Recommendation
# ---------------------------------------------------------

st.subheader("🤖 AI Assessment")

recommendation = review.get(
    "recommendation",
    "Not available"
)

st.info(
    f"**AI Recommendation:** {recommendation}"
)


with st.expander(
    "View Consolidated AI Assessment",
    expanded=True
):

    st.write(
        review.get(
            "synthesis",
            "No consolidated assessment available."
        )
    )


st.divider()


# ---------------------------------------------------------
# Grounded Chatbot
# ---------------------------------------------------------

st.subheader("💬 AegisAI Review Assistant")

st.write(
    "Ask questions about the case, supplied documents, "
    "or applicable PEIS policies."
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
            current_case_id
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
# Display Previous Messages
# ---------------------------------------------------------

for message in st.session_state.get(
    "decision_chat_messages",
    []
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
    placeholder="Why does this case require three vendor quotations?",
    key="decision_chat_input"
)

send_question = st.button(
    "Send Question",
    type="primary"
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
            "content": question
        }
    )

    with st.chat_message("user"):

        st.write(
            question
        )

    try:

        # -------------------------------------------------
        # Retrieve Policy Evidence
        # -------------------------------------------------

        policy_evidence = search_policies(
            question,
            top_k=6
        )


        policy_text = "\n\n".join(
            [
                f"{item['policy_id']} — "
                f"{item['policy_name']}\n"
                f"{item['section_id']} — "
                f"{item['section_title']}\n"
                f"{item['content']}"
                for item in policy_evidence
            ]
        )


        # -------------------------------------------------
        # Document Context
        # -------------------------------------------------

        document_text = "\n\n".join(
            [
                f"DOCUMENT: {doc['document_name']}\n"
                f"TYPE: {doc['document_type']}\n"
                f"CONTENT:\n{doc.get('extracted_text', '')}"
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
        # Gemini Prompt
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

{question}

Answer clearly and briefly.

When referring to a policy, cite its policy ID
and section ID, for example:

POL-001 P-02

Do not provide a final human decision.
"""


        # -------------------------------------------------
        # Gemini
        # -------------------------------------------------

        client = genai.Client(
            api_key=get_gemini_api_key()
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        answer = response.text


        # -------------------------------------------------
        # Display Assistant Response
        # -------------------------------------------------

        with st.chat_message("assistant"):

            st.write(
                answer
            )


        # -------------------------------------------------
        # Save Assistant Response
        # -------------------------------------------------

        st.session_state[
            "decision_chat_messages"
        ].append(
            {
                "role": "assistant",
                "content": answer
            }
        )


    except Exception as e:

        st.error(
            f"Assistant failed: {e}"
        )


st.divider()


# ---------------------------------------------------------
# Human Final Decision
# ---------------------------------------------------------

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
        .limit(1)
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
# Existing Final Decision
# ---------------------------------------------------------

if existing_decisions:

    previous_decision = existing_decisions[0]

    st.success(
        f"✅ Final decision already recorded: "
        f"{previous_decision.get('decision', 'N/A')}"
    )

    st.write(
        f"**Decision Date:** "
        f"{previous_decision.get('created_at', 'N/A')}"
    )

    st.write(
        f"**Reviewer Comments:** "
        f"{previous_decision.get('comments') or 'None'}"
    )

    st.info(
        "This case has already received a final human decision. "
        "A second final decision cannot be submitted."
    )


# ---------------------------------------------------------
# New Human Decision
# ---------------------------------------------------------

else:

    # -----------------------------------------------------
    # Evidence Gate Protection
    # -----------------------------------------------------

    gate = review.get(
        "evidence_gate"
    )

    # Supabase may return JSONB as a dictionary.
    # Handle string JSON safely as well.
    if isinstance(gate, str):

        try:

            gate = json.loads(gate)

        except Exception:

            gate = {}


    if not isinstance(gate, dict):

        gate = {}


    if not gate.get(
        "complete",
        False
    ):

        st.error(
            "🔴 FINAL DECISION LOCKED"
        )

        st.warning(
            "Mandatory policy-required evidence is incomplete. "
            "Please upload the missing evidence and run AI Case "
            "Review again before making the final decision."
        )

        st.subheader(
            "📋 Missing Evidence"
        )

        missing = gate.get(
            "missing",
            []
        )

        if not isinstance(
            missing,
            list
        ):

            missing = []


        if missing:

            for item in missing:

                st.write(
                    f"❌ **{item.get('name', 'Requirement')}**"
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

        st.stop()


    # -----------------------------------------------------
    # Evidence Complete
    # -----------------------------------------------------

    decision = st.radio(
        "Select Decision",
        [
            "Approve",
            "Return",
            "Reject"
        ],
        horizontal=True
    )


    comments = st.text_area(
        "Reviewer Comments",
        placeholder="Enter your decision comments..."
    )


    if decision in [
        "Return",
        "Reject"
    ] and not comments.strip():

        st.info(
            "Reviewer comments are required for "
            "Return or Reject."
        )


    # -----------------------------------------------------
    # Submit Decision
    # -----------------------------------------------------

    if st.button(
        "Submit Final Decision",
        type="primary",
        use_container_width=True
    ):

        if decision in [
            "Return",
            "Reject"
        ] and not comments.strip():

            st.error(
                "Please enter reviewer comments."
            )

            st.stop()


        try:

            # -------------------------------------------------
            # Save Human Decision
            # -------------------------------------------------

            supabase.table(
                "decisions"
            ).insert(
                {
                    "case_id": current_case_id,
                    "reviewer_id": st.session_state["user"].id,
                    "decision": decision,
                    "comments": comments.strip()
                }
            ).execute()


            # -------------------------------------------------
            # Update Case Status
            # -------------------------------------------------

            status_map = {
                "Approve": "APPROVED",
                "Return": "RETURNED",
                "Reject": "REJECTED"
            }

            new_status = status_map[
                decision
            ]


            supabase.table(
                "cases"
            ).update(
                {
                    "status": new_status
                }
            ).eq(
                "id",
                current_case_id
            ).execute()


            # -------------------------------------------------
            # Create Audit Log
            # -------------------------------------------------

            supabase.table(
                "audit_logs"
            ).insert(
                {
                    "case_id": current_case_id,
                    "user_id": st.session_state["user"].id,
                    "action": (
                        f"HUMAN_DECISION_"
                        f"{decision.upper()}"
                    ),
                    "details": (
                        f"Human reviewer selected "
                        f"{decision}. "
                        f"Comments: "
                        f"{comments.strip() or 'None'}"
                    )
                }
            ).execute()


            # -------------------------------------------------
            # Confirmation
            # -------------------------------------------------

            st.success(
                f"✅ Human decision saved successfully: "
                f"{decision}"
            )

            st.info(
                f"Case status updated to: {new_status}"
            )

            st.rerun()


        except Exception as e:

            st.error(
                f"Unable to save the human decision: {e}"
            )
