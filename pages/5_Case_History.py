from datetime import datetime, timezone

import streamlit as st
from pypdf import PdfReader

from database.supabase_client import get_supabase


st.set_page_config(
    page_title="Case History - AegisAI",
    page_icon="📚",
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


user = st.session_state["user"]
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

# Helpers

# ---------------------------------------------------------

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
            "+00:00",
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
Load the most recent evidence-change event.
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
            case_id,
        )
        .eq(
            "action",
            "EVIDENCE_CHANGED",
        )
        .order(
            "created_at",
            desc=True,
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
evidence_change,
):
"""
Determine whether evidence changed after the decision.
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


STEP_DEFINITIONS = [
("RAG", "RAG Policy Retrieval"),
("COMPLIANCE", "Compliance Agent"),
("FINANCIAL", "Financial Agent"),
("RISK", "Risk Agent"),
("SYNTHESIS", "Decision Synthesizer"),
("EVIDENCE", "Evidence Gate"),
]

def reset_ai_review(case_id):
"""
Invalidate the existing AI review whenever case evidence
changes.
"""


supabase.table("ai_review_steps").delete().eq(
    "case_id",
    case_id,
).execute()

supabase.table("ai_reviews").delete().eq(
    "case_id",
    case_id,
).execute()


def load_review_steps(case_id):
try:
response = (
supabase
.table("ai_review_steps")
.select("*")
.eq(
"case_id",
case_id,
)
.order(
"step_order",
)
.execute()
)


    return response.data or []

except Exception:
    return []


def parse_evidence_gate(review):
gate = review.get(
"evidence_gate",
{},
)


if isinstance(gate, str):
    try:
        import json

        gate = json.loads(gate)

    except Exception:
        gate = {}

if not isinstance(gate, dict):
    gate = {}

return gate


# ---------------------------------------------------------

# Header

# ---------------------------------------------------------

st.title("📚 Case History")

st.write(
"Review previous approval cases, AI recommendations, "
"human decisions, audit information, and manage "
"case documents."
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

st.divider()

nav_left, nav_right = st.columns(2)

with nav_left:
    if st.button(
        "← Decision",
        use_container_width=True,
        key="history_previous_empty",
    ):
        st.switch_page(
            "pages/4_Decision.py"
        )

with nav_right:
    if st.button(
        "Next: Report →",
        use_container_width=True,
        key="history_next_empty",
    ):
        st.switch_page(
            "pages/6_Report.py"
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
if str(
case.get("status", "")
).upper() == "APPROVED"
)

returned_cases = sum(
1
for case in cases
if str(
case.get("status", "")
).upper() == "RETURNED"
)

rejected_cases = sum(
1
for case in cases
if str(
case.get("status", "")
).upper() == "REJECTED"
)

col1, col2, col3, col4 = st.columns(4)

with col1:
st.metric(
"Total Cases",
total_cases,
)

with col2:
st.metric(
"Approved",
approved_cases,
)

with col3:
st.metric(
"Returned",
returned_cases,
)

with col4:
st.metric(
"Rejected",
rejected_cases,
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
    0,
)

try:
    amount_display = (
        f"PKR {float(amount):,.0f}"
    )

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
            case_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    reviews = (
        review_response.data or []
    )

except Exception:
    reviews = []


review = (
    reviews[0]
    if reviews
    else {}
)


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
        decision_response.data or []
    )

except Exception:
    decisions = []


human_decision = (
    decisions[0]
    if decisions
    else {}
)


# -----------------------------------------------------
# Load Workflow Checkpoints
# -----------------------------------------------------

review_steps = load_review_steps(
    case_id
)

step_status_map = {
    step.get("step_name"): step.get(
        "status",
        "PENDING",
    )
    for step in review_steps
}


# -----------------------------------------------------
# Case Header
# -----------------------------------------------------

with st.expander(
    f"{case.get('title', 'Untitled Case')} "
    f"— {amount_display}",
    expanded=False,
):

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(
            f"**Department:** "
            f"{case.get('department', 'N/A')}"
        )

    with col2:
        st.write(
            f"**Status:** {status}"
        )

    with col3:
        st.write(
            f"**Created:** "
            f"{case.get('created_at', 'N/A')}"
        )


    st.divider()


    # -------------------------------------------------
    # AI Workflow Status
    # -------------------------------------------------

    st.write("### 🔄 AI Review Workflow")

    if review_steps:

        completed_count = 0

        for step_name, label in STEP_DEFINITIONS:

            step_status = step_status_map.get(
                step_name,
                "PENDING",
            )

            if step_status == "COMPLETED":

                completed_count += 1

                st.success(
                    f"✅ {label} — COMPLETED"
                )

            elif step_status == "FAILED":

                st.error(
                    f"❌ {label} — FAILED"
                )

            elif step_status == "RUNNING":

                st.warning(
                    f"🔄 {label} — RUNNING"
                )

            else:

                st.info(
                    f"⏳ {label} — PENDING"
                )

        st.caption(
            f"{completed_count}/"
            f"{len(STEP_DEFINITIONS)} "
            "workflow steps completed."
        )

    elif review:

        st.success(
            "✅ AI review completed."
        )

    else:

        st.info(
            "No AI review has been completed."
        )


    # -------------------------------------------------
    # AI Recommendation
    # -------------------------------------------------

    st.write("### 🤖 AI Assessment")

    ai_recommendation = review.get(
        "recommendation",
        "No AI review available",
    )

    st.info(
        f"**AI Recommendation:** "
        f"{ai_recommendation}"
    )


    # -------------------------------------------------
    # Evidence Gate
    # -------------------------------------------------

    if review:

        gate = parse_evidence_gate(
            review
        )

        st.write("### 🔐 Evidence Gate")

        if gate.get(
            "complete",
            False,
        ):

            st.success(
                "✅ Evidence Gate PASSED"
            )

        else:

            missing_count = gate.get(
                "missing_count",
                0,
            )

            st.error(
                "🔴 Evidence Gate BLOCKED — "
                f"{missing_count} mandatory "
                "requirement(s) missing."
            )

            missing = gate.get(
                "missing",
                [],
            )

            if isinstance(
                missing,
                list,
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


    # -------------------------------------------------
    # Human Decision
    # -------------------------------------------------

    st.write(
        "### 👤 Human Decision"
    )

    latest_evidence_change = (
        load_latest_evidence_change(
            case_id
        )
    )

    decision_superseded = (
        decision_is_superseded(
            human_decision,
            latest_evidence_change,
        )
    )

    if human_decision:

        if decision_superseded:

            st.warning(
                "⚠️ **SUPERSEDED DECISION**"
            )

            st.write(
                f"**Previous Decision:** "
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

            st.info(
                "This decision remains in the historical record "
                "but no longer applies because the case evidence "
                "changed after the decision was recorded."
            )

        else:

            st.success(
                f"**Current Decision:** "
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
    # Case Documents
    # -------------------------------------------------

    st.divider()

    st.write("### 📎 Case Documents")

    try:

        document_response = (
            supabase
            .table("documents")
            .select("*")
            .eq(
                "case_id",
                case_id,
            )
            .order(
                "created_at",
            )
            .execute()
        )

        documents = (
            document_response.data or []
        )

    except Exception as e:

        documents = []

        st.error(
            f"Unable to load case documents: {e}"
        )


    if documents:

        for index, document in enumerate(
            documents,
            start=1,
        ):

            document_id = document.get(
                "id"
            )

            document_name = document.get(
                "document_name",
                "Unnamed document",
            )

            document_type = document.get(
                "document_type",
                "Other",
            )

            col_info, col_remove = (
                st.columns([5, 1])
            )

            with col_info:

                st.write(
                    f"**{index}. "
                    f"{document_name}**"
                )

                st.caption(
                    f"Document Type: "
                    f"{document_type}"
                )

            with col_remove:

                if st.button(
                    "🗑️ Remove",
                    use_container_width=True,
                    key=(
                        "history_remove_document_"
                        f"{document_id}"
                    ),
                ):

                    try:

                        (
                            supabase
                            .table("documents")
                            .delete()
                            .eq(
                                "id",
                                document_id,
                            )
                            .eq(
                                "case_id",
                                case_id,
                            )
                            .execute()
                        )

                        # Invalidate AI review because
                        # evidence has changed.
                        reset_ai_review(
                            case_id
                        )

                        st.session_state[
                            "current_case_id"
                        ] = case_id

                        st.session_state[
                            "documents_changed_case_id"
                        ] = case_id

                        st.success(
                            f"{document_name} "
                            "was removed successfully."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            "Unable to remove document: "
                            f"{e}"
                        )

    else:

        st.info(
            "No documents are currently uploaded "
            "for this case."
        )


    # -------------------------------------------------
    # Upload Replacement Document
    # -------------------------------------------------

    st.write(
        "### ➕ Upload / Replace Document"
    )

    if review or human_decision:

        st.warning(
            "Changing case documents invalidates "
            "the existing AI assessment. A new AI "
            "review is required before relying on "
            "the updated case."
        )


    upload_col1, upload_col2 = (
        st.columns([2, 3])
    )

    with upload_col1:

        replacement_type = st.selectbox(
            "Document Type",
            [
                "Purchase Request",
                "Business Justification",
                "Vendor Quotation",
                "Technical Evaluation",
                "Comparative Statement",
                "Approval Request",
                "Other",
            ],
            key=(
                f"history_document_type_"
                f"{case_id}"
            ),
        )

    with upload_col2:

        replacement_file = st.file_uploader(
            "Select PDF document",
            type=["pdf"],
            key=(
                f"history_upload_"
                f"{case_id}"
            ),
        )


    if replacement_file:

        st.caption(
            f"Selected: "
            f"**{replacement_file.name}**"
        )

        if st.button(
            "📤 Upload & Extract Text",
            type="primary",
            use_container_width=True,
            key=(
                f"history_upload_button_"
                f"{case_id}"
            ),
        ):

            try:

                # -------------------------------------
                # Duplicate Filename Check
                # -------------------------------------

                duplicate = any(
                    str(
                        document.get(
                            "document_name",
                            "",
                        )
                    ).strip().lower()
                    == replacement_file.name.strip().lower()
                    for document in documents
                )

                if duplicate:

                    st.error(
                        f"A document named "
                        f"'{replacement_file.name}' "
                        "is already uploaded for this "
                        "case. Remove the existing file "
                        "first if you want to replace it."
                    )

                    st.stop()


                # -------------------------------------
                # Read PDF
                # -------------------------------------

                reader = PdfReader(
                    replacement_file
                )

                extracted_pages = []

                for page in reader.pages:

                    text = page.extract_text()

                    if text:

                        extracted_pages.append(
                            text
                        )

                extracted_text = (
                    "\n\n".join(
                        extracted_pages
                    )
                )


                # -------------------------------------
                # Check Extracted Text
                # -------------------------------------

                if not extracted_text.strip():

                    st.error(
                        "No selectable text was found "
                        "in this PDF. OCR is not available "
                        "in the current MVP."
                    )

                    st.stop()


                # -------------------------------------
                # Save Document
                # -------------------------------------

                upload_response = (
                    supabase
                    .table("documents")
                    .insert(
                        {
                            "case_id": case_id,
                            "document_name": (
                                replacement_file.name
                            ),
                            "document_type": (
                                replacement_type
                            ),
                            "extracted_text": (
                                extracted_text
                            ),
                        }
                    )
                    .execute()
                )


                if upload_response.data:

                    # Invalidate existing AI review
                    # because evidence changed.
                    reset_ai_review(
                        case_id
                    )

                    st.session_state[
                        "current_case_id"
                    ] = case_id

                    st.session_state[
                        "documents_changed_case_id"
                    ] = case_id

                    st.success(
                        f"{replacement_file.name} "
                        "uploaded successfully."
                    )

                    st.info(
                        "Existing AI review has been "
                        "invalidated. Run a new AI review "
                        "for this updated evidence."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Document could not be saved."
                    )

            except Exception as e:

                st.error(
                    f"Error processing document: {e}"
                )


    # -------------------------------------------------
    # Open Case for Re-Review
    # -------------------------------------------------

    if (
        st.session_state.get(
            "documents_changed_case_id"
        )
        == case_id
    ):

        st.info(
            "Documents for this case have changed. "
            "Run a new AI Case Review before relying "
            "on the previous assessment."
        )

        if st.button(
            "📝 Open Case for New AI Review",
            use_container_width=True,
            key=(
                f"open_case_for_review_"
                f"{case_id}"
            ),
        ):

            st.session_state[
                "current_case_id"
            ] = case_id

            st.switch_page(
                "pages/2_Create_Case.py"
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
                    "No synthesis available.",
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
                "No description available.",
            )
        )


st.divider()

st.caption(
"AegisAI Case History — Human decisions are "
"authoritative and AI recommendations are advisory."
)

# ---------------------------------------------------------

# PAGE NAVIGATION

# ---------------------------------------------------------

st.divider()

nav_left, nav_right = st.columns(2)

with nav_left:


if st.button(
    "← Decision",
    use_container_width=True,
    key="history_previous",
):

    st.switch_page(
        "pages/4_Decision.py"
    )


with nav_right:


if st.button(
    "Next: Report →",
    use_container_width=True,
    key="history_next",
):

    st.switch_page(
        "pages/6_Report.py"
    )
