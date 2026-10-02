import streamlit as st

from services.ai_review import run_ai_case_review
from pypdf import PdfReader

from database.supabase_client import get_supabase


st.set_page_config(
    page_title="Create Case - AegisAI",
    page_icon="📝",
    layout="wide"
)


# ==========================================
# AUTH CHECK
# ==========================================

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):
    st.warning("Please login first.")
    st.stop()


user = st.session_state["user"]

supabase = get_supabase()


# ==========================================
# HEADER
# ==========================================

st.title("📝 Create Approval Case")

st.write(
    "Create a procurement or capital expenditure "
    "approval case and upload its supporting documents."
)

st.divider()


# ==========================================
# CREATE CASE
# ==========================================

st.subheader("1. Request Information")

with st.form("create_case_form"):

    title = st.text_input(
        "Request Title",
        placeholder="e.g. Industrial Testing Equipment Procurement"
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
        placeholder="e.g. Engr. Ahmed Raza, Manager Engineering"
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


# ==========================================
# SAVE CASE
# ==========================================

if submitted:

    if not title.strip():
        st.error("Please enter the request title.")
        st.stop()

    if not requester.strip():
        st.error("Please enter the requester.")
        st.stop()

    if amount <= 0:
        st.error("Amount must be greater than zero.")
        st.stop()

    if not description.strip():
        st.error("Please enter the request description.")
        st.stop()

    if not business_justification.strip():
        st.error("Please enter the business justification.")
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

            st.session_state["current_case_id"] = case_id

            st.session_state.pop(
                "ai_case_review",
                None
            )

            st.session_state.pop(
                "ai_case_review_id",
                None
            )

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

    except Exception as e:

        st.error(
            f"Error creating case: {str(e)}"
        )


# ==========================================
# DOCUMENT UPLOAD
# ==========================================

if "current_case_id" in st.session_state:

    case_id = st.session_state["current_case_id"]

    st.divider()

    st.subheader("2. Upload Supporting Documents")

    st.write(
        "Upload the available PDF documents for this case. "
        "The AI Review will determine which evidence is required."
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
        ]
    )

    uploaded_file = st.file_uploader(
        "Select PDF document",
        type=["pdf"]
    )

    if uploaded_file:

        st.write(
            f"Selected: **{uploaded_file.name}**"
        )

        if st.button(
            "📤 Upload & Extract Text",
            type="primary"
        ):

            try:

                # ------------------------------------------
                # READ PDF
                # ------------------------------------------

                reader = PdfReader(
                    uploaded_file
                )

                extracted_pages = []

                for page in reader.pages:

                    text = page.extract_text()

                    if text:
                        extracted_pages.append(text)

                extracted_text = "\n\n".join(
                    extracted_pages
                )

                # ------------------------------------------
                # CHECK TEXT
                # ------------------------------------------

                if not extracted_text.strip():

                    st.warning(
                        "No selectable text was found in this PDF. "
                        "OCR is not available in the current MVP."
                    )

                    st.stop()

                # ------------------------------------------
                # SAVE DOCUMENT
                # ------------------------------------------

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

                    st.success(
                        f"{uploaded_file.name} uploaded successfully."
                    )

                    st.info(
                        f"Extracted approximately "
                        f"{len(extracted_text):,} characters."
                    )

                else:

                    st.error(
                        "Document could not be saved."
                    )

            except Exception as e:

                st.error(
                    f"Error processing document: {str(e)}"
                )


# ==========================================
# CURRENT CASE DOCUMENTS
# ==========================================

if "current_case_id" in st.session_state:

    case_id = st.session_state["current_case_id"]

    st.divider()

    st.subheader("3. Uploaded Documents")

    try:

        response = (
            supabase
            .table("documents")
            .select("*")
            .eq("case_id", case_id)
            .order("created_at")
            .execute()
        )

        documents = response.data or []

        if documents:

            for index, document in enumerate(
                documents,
                start=1
            ):

                st.write(
                    f"**{index}. "
                    f"{document.get('document_name', '-')}"
                    f"** — "
                    f"{document.get('document_type', '-')}"
                )

        else:

            st.info(
                "No documents uploaded yet."
            )

    except Exception as e:

        st.error(
            f"Unable to load documents: {str(e)}"
        )


# ==========================================
# AI CASE REVIEW
# ==========================================

if "current_case_id" in st.session_state:

    case_id = st.session_state["current_case_id"]

    st.divider()

    st.subheader("4. AI Case Review")

    st.info(
        "Run the AI review after uploading the available "
        "case documents. AegisAI will retrieve the applicable "
        "policy evidence, determine the required evidence, "
        "and run the Compliance, Financial, Risk, and "
        "Decision Synthesizer agents."
    )

    if st.button(
        "🚀 Run AI Case Review",
        type="primary",
        use_container_width=True
    ):

        try:

            # ------------------------------------------
            # LOAD CASE
            # ------------------------------------------

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

            # ------------------------------------------
            # LOAD DOCUMENTS
            # ------------------------------------------

            document_response = (
                supabase
                .table("documents")
                .select("*")
                .eq(
                    "case_id",
                    case_id
                )
                .execute()
            )

            current_documents = (
                document_response.data or []
            )

            # ------------------------------------------
            # RUN AI REVIEW
            # ------------------------------------------

            with st.spinner(
                "Running policy retrieval and multi-agent review..."
            ):

                review = run_ai_case_review(
                    current_case,
                    current_documents
                )

            # ------------------------------------------
            # KEEP REVIEW IN SESSION
            # ------------------------------------------

            st.session_state["ai_case_review"] = review

            st.session_state["ai_case_review_id"] = case_id

            # ------------------------------------------
            # SAVE AI REVIEW
            # ------------------------------------------

            ai_review_response = (
                supabase
                .table("ai_reviews")
                .insert({
                    "case_id": case_id,

                    "compliance_result": review.get(
                        "compliance",
                        ""
                    ),

                    "financial_result": review.get(
                        "financial",
                        ""
                    ),

                    "risk_result": review.get(
                        "risk",
                        ""
                    ),

                    "synthesis": review.get(
                        "synthesis",
                        ""
                    ),

                    "recommendation": review.get(
                        "synthesis",
                        ""
                    ),

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

            # ------------------------------------------
            # CHECK DATABASE SAVE
            # ------------------------------------------

            if not ai_review_response.data:

                st.warning(
                    "AI review completed, but the review "
                    "could not be saved to the database."
                )

            else:

                st.success(
                    "AI Case Review completed successfully."
                )

        except Exception as e:

            st.error(
                f"AI review failed: {str(e)}"
            )


# ==========================================
# DISPLAY AI REVIEW
# ==========================================

if (
    st.session_state.get("ai_case_review_id")
    == st.session_state.get("current_case_id")
    and "ai_case_review" in st.session_state
):

    review = st.session_state["ai_case_review"]

    st.divider()

    st.subheader("📋 Evidence Requirements")

    requirements = review.get(
        "requirements",
        []
    )

    if requirements:

        for item in requirements:

            if item.get("status") == "COMPLETE":

                st.success(
                    f"✅ {item.get('name', 'Requirement')}"
                )

            else:

                st.error(
                    f"❌ {item.get('name', 'Requirement')} — MISSING"
                )

            if item.get("reason"):

                st.caption(
                    item["reason"]
                )

    else:

        st.info(
            "No mandatory evidence requirements were "
            "identified from the retrieved policy evidence."
        )

    # ==========================================
    # EVIDENCE GATE
    # ==========================================

    gate = review.get(
        "evidence_gate",
        {}
    )

    st.subheader("🔐 Evidence Gate")

    if gate.get("complete", False):

        st.success(
            "✅ Evidence Gate PASSED — all identified "
            "mandatory evidence is available."
        )

    else:

        st.error(
            "🔴 Evidence Gate BLOCKED — mandatory "
            "policy-required evidence is missing."
        )

        for item in gate.get("missing", []):

            st.write(
                f"• **{item.get('name', 'Requirement')}**"
            )

            if item.get("reason"):

                st.caption(
                    item["reason"]
                )
```
