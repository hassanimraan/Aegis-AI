import streamlit as st

from services.ai_review import run_ai_case_review
from pypdf import PdfReader

from database.supabase_client import get_supabase


st.set_page_config(
    page_title="Create Case - AegisAI",
    page_icon="📝",
    layout="wide"
)


# =========================================================
# AUTH CHECK
# =========================================================

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning("Please login first.")
    st.stop()


user = st.session_state["user"]

supabase = get_supabase()


# =========================================================
# CONSTANTS
# =========================================================

REVIEW_STEPS = [
    ("RAG", "Policy Retrieval"),
    ("COMPLIANCE", "Compliance Agent"),
    ("FINANCIAL", "Financial Agent"),
    ("RISK", "Risk Agent"),
    ("SYNTHESIS", "Decision Synthesizer"),
    ("EVIDENCE", "Evidence Gate"),
]


# =========================================================
# HELPERS
# =========================================================

def clear_session_review():
    st.session_state.pop(
        "ai_case_review",
        None
    )

    st.session_state.pop(
        "ai_case_review_id",
        None
    )


def reset_case_review(case_id):
    """
    Clears previous AI checkpoints and final AI review.

    Used when case evidence changes or the user explicitly
    requests a complete restart.
    """

    try:

        (
            supabase
            .table("ai_review_steps")
            .delete()
            .eq(
                "case_id",
                case_id
            )
            .execute()
        )

        (
            supabase
            .table("ai_reviews")
            .delete()
            .eq(
                "case_id",
                case_id
            )
            .execute()
        )

        clear_session_review()

        return True

    except Exception as error:

        st.error(
            f"Unable to reset the AI review: {error}"
        )

        return False


def record_evidence_change(
    case_id,
    user_id,
    action,
    document_name,
    document_type=None,
):
    """
    Records that case evidence changed.

    This audit event is used to determine whether a previous
    human decision is still applicable to the current evidence.
    """

    try:

        details = (
            f"Case evidence changed. "
            f"Action: {action}. "
            f"Document: {document_name or 'Unknown'}."
        )

        if document_type:

            details += (
                f" Document Type: {document_type}."
            )

        response = (
            supabase
            .table("audit_logs")
            .insert({
                "case_id": case_id,
                "user_id": user_id,
                "action": "EVIDENCE_CHANGED",
                "details": details,
            })
            .execute()
        )

        return bool(response.data)

    except Exception as error:

        st.error(
            f"Unable to record evidence-change audit event: {error}"
        )

        return False


def get_review_steps(case_id):
    """
    Load persistent AI workflow checkpoints.
    """

    try:

        response = (
            supabase
            .table("ai_review_steps")
            .select("*")
            .eq(
                "case_id",
                case_id
            )
            .order(
                "step_order"
            )
            .execute()
        )

        return response.data or []

    except Exception:

        return []


def step_status_map(case_id):
    """
    Convert checkpoint records into:

        {
            "RAG": {...},
            "COMPLIANCE": {...}
        }
    """

    records = get_review_steps(
        case_id
    )

    return {
        record.get("step_name"): record
        for record in records
    }


def display_review_progress(case_id):
    """
    Display the persistent six-step AI workflow.
    """

    st.subheader(
        "AI Review Progress"
    )

    steps = step_status_map(
        case_id
    )

    completed_count = sum(
        1
        for step_name, _ in REVIEW_STEPS
        if steps.get(
            step_name,
            {}
        ).get("status") == "COMPLETED"
    )

    progress_value = (
        completed_count / len(REVIEW_STEPS)
    )

    st.progress(
        progress_value,
        text=(
            f"{completed_count}/"
            f"{len(REVIEW_STEPS)} steps completed"
        )
    )

    for step_name, display_name in REVIEW_STEPS:

        record = steps.get(
            step_name
        )

        if not record:

            st.info(
                f"⚪ {display_name} — Pending"
            )

            continue

        status = record.get(
            "status",
            "PENDING"
        )

        provider = record.get(
            "provider"
        )

        model = record.get(
            "model"
        )

        if status == "COMPLETED":

            provider_text = ""

            if provider:

                provider_text = (
                    f" | Provider: {provider}"
                )

            st.success(
                f"🟢 {display_name} — Completed"
                f"{provider_text}"
            )

        elif status == "RUNNING":

            st.warning(
                f"🟡 {display_name} — Running"
            )

        elif status == "FAILED":

            st.error(
                f"🔴 {display_name} — Failed"
            )

            error_text = record.get(
                "error"
            )

            if error_text:

                st.caption(
                    f"Error: {error_text}"
                )

        else:

            st.info(
                f"⚪ {display_name} — Pending"
            )

        if (
            model
            and status == "COMPLETED"
        ):

            st.caption(
                f"Model: {model}"
            )


def extract_review_text(result):
    """
    Agents return a router result dictionary.

    This helper extracts the actual analysis text.
    """

    if isinstance(
        result,
        dict
    ):

        return result.get(
            "text",
            ""
        )

    if result is None:

        return ""

    return str(result)


# =========================================================
# HEADER
# =========================================================

st.title(
    "📝 Create Approval Case"
)

st.write(
    "Create a procurement or capital expenditure "
    "approval case and upload its supporting documents."
)

st.divider()


# =========================================================
# 1. CREATE CASE
# =========================================================

st.subheader(
    "1. Request Information"
)

with st.form(
    "create_case_form"
):

    title = st.text_input(
        "Request Title",
        placeholder=(
            "e.g. Industrial Testing Equipment Procurement"
        )
    )

    department = st.selectbox(
        "Department",
        [
            "Engineering",
            "Procurement",
            "Finance",
            "Projects",
            "Administration",
            "HR"
        ]
    )

    requester = st.text_input(
        "Requester",
        placeholder=(
            "e.g. Engr. Ahmed Raza, Manager Engineering"
        )
    )

    amount = st.number_input(
        "Amount (PKR)",
        min_value=0.0,
        step=1000.0,
        format="%.2f"
    )

    request_type = st.selectbox(
        "Request Type",
        [
            "Capital Expenditure",
            "Procurement",
            "Other"
        ]
    )

    description = st.text_area(
        "Request Description"
    )

    business_justification = st.text_area(
        "Business Justification"
    )

    submitted = st.form_submit_button(
        "Create Approval Case",
        type="primary",
        use_container_width=True
    )


# =========================================================
# SAVE CASE
# =========================================================

if submitted:

    if not title.strip():

        st.error(
            "Please enter the request title."
        )

        st.stop()

    if not requester.strip():

        st.error(
            "Please enter the requester."
        )

        st.stop()

    if amount <= 0:

        st.error(
            "Amount must be greater than zero."
        )

        st.stop()

    if not description.strip():

        st.error(
            "Please enter the request description."
        )

        st.stop()

    if not business_justification.strip():

        st.error(
            "Please enter the business justification."
        )

        st.stop()

    try:

        response = (
            supabase
            .table("cases")
            .insert({
                "user_id": user.id,
                "title": title.strip(),
                "department": department,
                "amount": amount,
                "description": (
                    f"Request Type: {request_type}\n\n"
                    f"Requester: {requester.strip()}\n\n"
                    f"{description.strip()}\n\n"
                    f"Business Justification:\n"
                    f"{business_justification.strip()}"
                ),
                "status": "DRAFT"
            })
            .execute()
        )

        if response.data:

            case_id = response.data[0]["id"]

            st.session_state[
                "current_case_id"
            ] = case_id

            clear_session_review()

            st.success(
                "Approval case created successfully."
            )

            st.info(
                f"Case ID: {case_id}"
            )

        else:

            st.error(
                "Case could not be created."
            )

    except Exception as error:

        st.error(
            f"Error creating case: {error}"
        )


# =========================================================
# CURRENT CASE
# =========================================================

if "current_case_id" in st.session_state:

    case_id = st.session_state[
        "current_case_id"
    ]


    # =====================================================
    # 2. DOCUMENT UPLOAD
    # =====================================================

    st.divider()

    st.subheader(
        "2. Upload Supporting Documents"
    )

    st.write(
        "Upload the available PDF documents for this case. "
        "The AI Review will determine which evidence is required "
        "from the applicable policy and case scenario."
    )

    document_type = st.selectbox(
        "Document Type",
        [
            "Purchase Request",
            "Business Justification",
            "Vendor Quotation",
            "Technical Evaluation",
            "Comparative Statement",
            "Approval Request",
            "Other"
        ],
        key="document_type_selector"
    )

    uploaded_file = st.file_uploader(
        "Select PDF document",
        type=["pdf"],
        key="case_pdf_uploader"
    )

    if uploaded_file:

        st.write(
            f"Selected: **{uploaded_file.name}**"
        )

        if st.button(
            "📤 Upload & Extract Text",
            type="primary",
            key="upload_document_button"
        ):

            try:

                reader = PdfReader(
                    uploaded_file
                )

                extracted_pages = []

                for page in reader.pages:

                    text = page.extract_text()

                    if text:

                        extracted_pages.append(
                            text
                        )

                extracted_text = "\n\n".join(
                    extracted_pages
                )

                if not extracted_text.strip():

                    st.warning(
                        "No selectable text was found in this PDF. "
                        "OCR is not available in the current MVP."
                    )

                    st.stop()

                response = (
                    supabase
                    .table("documents")
                    .insert({
                        "case_id": case_id,
                        "document_name": uploaded_file.name,
                        "document_type": document_type,
                        "extracted_text": extracted_text
                    })
                    .execute()
                )

                if response.data:

                    # -------------------------------------------------
                    # Evidence has changed.
                    # Existing AI analysis is no longer valid.
                    # -------------------------------------------------

                    audit_recorded = record_evidence_change(
                        case_id=case_id,
                        user_id=user.id,
                        action="DOCUMENT_UPLOADED",
                        document_name=uploaded_file.name,
                        document_type=document_type,
                    )

                    review_reset = reset_case_review(
                        case_id
                    )

                    if review_reset:

                        st.success(
                            f"{uploaded_file.name} uploaded successfully."
                        )

                        st.info(
                            f"Extracted approximately "
                            f"{len(extracted_text):,} characters."
                        )

                        st.info(
                            "Previous AI analysis was cleared because "
                            "the case evidence changed. A new review "
                            "will start from the beginning."
                        )

                        if not audit_recorded:

                            st.warning(
                                "The evidence-change audit event could "
                                "not be recorded. Please check the "
                                "audit log before proceeding."
                            )

                        st.rerun()

                    else:

                        st.error(
                            "The document was uploaded, but the previous "
                            "AI review could not be cleared. Please do "
                            "not make a human decision until the AI "
                            "review is successfully restarted."
                        )

                else:

                    st.error(
                        "Document could not be saved."
                    )

            except Exception as error:

                st.error(
                    f"Error processing document: {error}"
                )


    # =====================================================
    # 3. CURRENT CASE DOCUMENTS
    # =====================================================

    st.divider()

    st.subheader(
        "3. Uploaded Documents"
    )

    try:

        response = (
            supabase
            .table("documents")
            .select("*")
            .eq(
                "case_id",
                case_id
            )
            .order(
                "created_at"
            )
            .execute()
        )

        documents = response.data or []

        if documents:

            for index, document in enumerate(
                documents,
                start=1
            ):

                document_id = document.get(
                    "id"
                )

                document_name = document.get(
                    "document_name",
                    "-"
                )

                document_type_value = document.get(
                    "document_type",
                    "-"
                )

                col_info, col_remove = st.columns(
                    [5, 1]
                )

                with col_info:

                    st.write(
                        f"**{index}. {document_name}**"
                    )

                    st.caption(
                        f"Document Type: {document_type_value}"
                    )

                with col_remove:

                    if st.button(
                        "🗑️ Remove",
                        key=f"remove_document_{document_id}",
                        use_container_width=True
                    ):

                        try:

                            delete_response = (
                                supabase
                                .table("documents")
                                .delete()
                                .eq(
                                    "id",
                                    document_id
                                )
                                .eq(
                                    "case_id",
                                    case_id
                                )
                                .execute()
                            )

                            if delete_response.data:

                                # -------------------------------------------------
                                # Evidence has changed.
                                # Existing AI analysis is no longer valid.
                                # -------------------------------------------------

                                audit_recorded = record_evidence_change(
                                    case_id=case_id,
                                    user_id=user.id,
                                    action="DOCUMENT_REMOVED",
                                    document_name=document_name,
                                    document_type=document_type_value,
                                )

                                review_reset = reset_case_review(
                                    case_id
                                )

                                if review_reset:

                                    st.success(
                                        f"{document_name} removed successfully."
                                    )

                                    st.info(
                                        "Previous AI analysis was cleared "
                                        "because the case evidence changed. "
                                        "A new review is required."
                                    )

                                    if not audit_recorded:

                                        st.warning(
                                            "The evidence-change audit event "
                                            "could not be recorded. Please "
                                            "check the audit log before "
                                            "proceeding."
                                        )

                                    st.rerun()

                                else:

                                    st.error(
                                        "The document was removed, but the "
                                        "previous AI review could not be "
                                        "cleared. Please do not make a human "
                                        "decision until the AI review is "
                                        "successfully restarted."
                                    )

                            else:

                                st.warning(
                                    "Document could not be removed."
                                )

                        except Exception as error:

                            st.error(
                                f"Error removing document: {error}"
                            )

        else:

            st.info(
                "No documents uploaded yet."
            )

    except Exception as error:

        st.error(
            f"Unable to load documents: {error}"
        )


    # =====================================================
    # 4. AI CASE REVIEW
    # =====================================================

    st.divider()

    st.subheader(
        "4. AI Case Review"
    )

    st.info(
        "AegisAI processes the review sequentially. "
        "Each completed step is saved to Supabase. "
        "If a provider or step fails, running the review again "
        "resumes from the last incomplete step."
    )


    # -----------------------------------------------------
    # SHOW EXISTING PROGRESS
    # -----------------------------------------------------

    existing_steps = get_review_steps(
        case_id
    )

    if existing_steps:

        display_review_progress(
            case_id
        )

        st.divider()


    # -----------------------------------------------------
    # REVIEW CONTROLS
    # -----------------------------------------------------

    review_col, restart_col = st.columns(
        [3, 1]
    )

    with review_col:

        run_review = st.button(
            "🚀 Run / Resume AI Case Review",
            type="primary",
            use_container_width=True,
            key="run_ai_case_review"
        )

    with restart_col:

        restart_review = st.button(
            "🔄 Restart",
            use_container_width=True,
            key="restart_ai_case_review"
        )


    # -----------------------------------------------------
    # EXPLICIT RESTART
    # -----------------------------------------------------

    if restart_review:

        if reset_case_review(
            case_id
        ):

            st.success(
                "AI review checkpoints cleared. "
                "The next review will start from the beginning."
            )

            st.rerun()


    # -----------------------------------------------------
    # RUN / RESUME REVIEW
    # -----------------------------------------------------

    if run_review:

        try:

            # ---------------------------------------------
            # LOAD CASE
            # ---------------------------------------------

            case_response = (
                supabase
                .table("cases")
                .select("*")
                .eq(
                    "id",
                    case_id
                )
                .single()
                .execute()
            )

            current_case = case_response.data

            if not current_case:

                st.error(
                    "Unable to load the current case."
                )

                st.stop()


            # ---------------------------------------------
            # LOAD DOCUMENTS
            # ---------------------------------------------

            document_response = (
                supabase
                .table("documents")
                .select("*")
                .eq(
                    "case_id",
                    case_id
                )
                .order(
                    "created_at"
                )
                .execute()
            )

            current_documents = (
                document_response.data or []
            )


            # ---------------------------------------------
            # RUN WORKFLOW
            # ---------------------------------------------

            progress_placeholder = st.empty()

            status_placeholder = st.empty()

            progress_placeholder.progress(
                0,
                text="Starting AegisAI review..."
            )

            status_placeholder.info(
                "The review will resume from the first "
                "incomplete checkpoint."
            )

            review = run_ai_case_review(
                current_case,
                current_documents
            )


            # ---------------------------------------------
            # STORE COMPLETE REVIEW IN SESSION
            # ---------------------------------------------

            st.session_state[
                "ai_case_review"
            ] = review

            st.session_state[
                "ai_case_review_id"
            ] = case_id


            # ---------------------------------------------
            # EXTRACT FINAL TEXT RESULTS
            # ---------------------------------------------

            compliance_text = extract_review_text(
                review.get("compliance")
            )

            financial_text = extract_review_text(
                review.get("financial")
            )

            risk_text = extract_review_text(
                review.get("risk")
            )

            synthesis_text = extract_review_text(
                review.get("synthesis")
            )


            # ---------------------------------------------
            # SAVE FINAL AI REVIEW
            # ---------------------------------------------
            #
            # Create the new complete review first.
            # Then remove older review records for this case.
            # This prevents duplicate ai_reviews when the user
            # presses Run / Resume again after completion.
            #

            ai_review_response = (
                supabase
                .table("ai_reviews")
                .insert({
                    "case_id": case_id,

                    "compliance_result": compliance_text,

                    "financial_result": financial_text,

                    "risk_result": risk_text,

                    "synthesis": synthesis_text,

                    "recommendation": synthesis_text,

                    "requirements": review.get(
                        "requirements",
                        []
                    ),

                    "evidence_gate": review.get(
                        "evidence_gate",
                        {}
                    )
                })
                .execute()
            )

            if ai_review_response.data:

                new_review_id = (
                    ai_review_response.data[0].get(
                        "id"
                    )
                )

                if new_review_id:

                    (
                        supabase
                        .table("ai_reviews")
                        .delete()
                        .eq(
                            "case_id",
                            case_id
                        )
                        .neq(
                            "id",
                            new_review_id
                        )
                        .execute()
                    )


            # ---------------------------------------------
            # FINAL CHECK
            # ---------------------------------------------

            if not ai_review_response.data:

                st.warning(
                    "AI review completed, but the final review "
                    "could not be saved to the database."
                )

            else:

                progress_placeholder.progress(
                    1.0,
                    text="6/6 steps completed"
                )

                status_placeholder.success(
                    "AegisAI Case Review completed successfully."
                )

                st.success(
                    "✅ Complete AI Case Review saved successfully."
                )

                st.rerun()


        except Exception as error:

            st.error(
                f"AI review stopped: {error}"
            )

            st.info(
                "Your completed checkpoints have been preserved. "
                "You can press 'Run / Resume AI Case Review' again "
                "to continue from the failed step."
            )

            display_review_progress(
                case_id
            )


    # =====================================================
    # DISPLAY CURRENT AI REVIEW
    # =====================================================

    if (
        st.session_state.get(
            "ai_case_review_id"
        )
        == case_id
        and
        "ai_case_review"
        in st.session_state
    ):

        review = st.session_state[
            "ai_case_review"
        ]

        st.divider()

        st.subheader(
            "📋 Evidence Requirements"
        )

        requirements = review.get(
            "requirements",
            []
        )

        if requirements:

            for item in requirements:

                if item.get(
                    "status"
                ) == "COMPLETE":

                    st.success(
                        f"✅ {item.get('name', 'Requirement')}"
                    )

                else:

                    st.error(
                        f"❌ {item.get('name', 'Requirement')} — MISSING"
                    )

                if item.get(
                    "reason"
                ):

                    st.caption(
                        item["reason"]
                    )

        else:

            st.info(
                "No mandatory evidence requirements were "
                "identified from the retrieved policy evidence."
            )


        # =================================================
        # EVIDENCE GATE
        # =================================================

        gate = review.get(
            "evidence_gate",
            {}
        )

        st.subheader(
            "🔐 Evidence Gate"
        )

        if gate.get(
            "complete",
            False
        ):

            st.success(
                "✅ Evidence Gate PASSED — all identified "
                "mandatory evidence is available."
            )

        else:

            st.error(
                "🔴 Evidence Gate BLOCKED — mandatory "
                "policy-required evidence is missing."
            )

            for item in gate.get(
                "missing",
                []
            ):

                st.write(
                    f"• **{item.get('name', 'Requirement')}**"
                )

                if item.get(
                    "reason"
                ):

                    st.caption(
                        item["reason"]
                    )


# =========================================================
# PAGE NAVIGATION
# =========================================================

st.divider()

nav_left, nav_right = st.columns(
    [1, 1]
)

with nav_left:

    if st.button(
        "← Dashboard",
        use_container_width=True,
        key="create_case_previous"
    ):

        st.switch_page(
            "pages/1_Dashboard.py"
        )


with nav_right:

    if st.button(
        "Next: Case Review →",
        use_container_width=True,
        key="create_case_next"
    ):

        st.switch_page(
            "pages/3_Case_Review.py"
        )
