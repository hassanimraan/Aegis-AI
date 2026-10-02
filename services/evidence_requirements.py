"""
AegisAI - Policy-Driven Evidence Requirements

Final production evidence-requirement engine.

Design principles:
1. Requirements are derived from retrieved PEIS policy evidence
   and the actual case context.
2. AegisAI must NOT impose a universal document checklist.
3. Quotation requirements apply only when the supplied policy
   establishes the applicable threshold/rule.
4. A single-source route does NOT remove the quotation requirement
   merely because the words "single source" appear somewhere.
   There must be explicit justification/approval evidence.
5. Conditional requirements such as Technical Evaluation are
   activated only when the policy and case context support them.
6. AI analysis itself is never treated as documentary evidence.
7. The returned objects are JSON-serializable for Supabase JSONB.
"""

import re


# ==========================================================
# NORMALIZATION HELPERS
# ==========================================================

def _text(value):
    """Return normalized lowercase text."""
    return str(value or "").strip().lower()


def _amount(case_data):
    """Safely convert case amount to float."""
    try:
        value = case_data.get("amount")
        if value is None or str(value).strip() == "":
            return 0.0

        cleaned = (
            str(value)
            .replace(",", "")
            .replace("PKR", "")
            .replace("pkr", "")
            .strip()
        )

        return float(cleaned)

    except (TypeError, ValueError):
        return 0.0


def _document_type(document):
    """Return normalized document type."""
    return _text(document.get("document_type"))


def _document_text(document):
    """Return searchable text from an uploaded document."""
    return _text(
        " ".join(
            [
                str(document.get("document_name", "")),
                str(document.get("document_type", "")),
                str(document.get("extracted_text", "")),
            ]
        )
    )


def _all_policy_text(policy_evidence):
    """Combine retrieved policy evidence into normalized text."""
    return "\n".join(
        _text(item.get("content"))
        for item in policy_evidence
        if item.get("content")
    )


def _has_policy_phrase(policy_text, phrases):
    """Return True when any supplied phrase exists in policy text."""
    return any(
        phrase.lower() in policy_text
        for phrase in phrases
    )


def _has_document_type(documents, document_type):
    """Check whether at least one document has the specified type."""
    target = _text(document_type)

    return any(
        _document_type(document) == target
        for document in documents
    )


def _document_count(documents, document_type):
    """Count uploaded documents of a specific type."""
    target = _text(document_type)

    return sum(
        1
        for document in documents
        if _document_type(document) == target
    )


# ==========================================================
# CASE CONTEXT
# ==========================================================

def _case_text(case_data):
    """Build normalized searchable case text."""
    return _text(
        " ".join(
            [
                str(case_data.get("title", "")),
                str(case_data.get("description", "")),
                str(case_data.get("business_justification", "")),
                str(case_data.get("request_type", "")),
            ]
        )
    )


def _is_capital_expenditure(case_data, case_text):
    """Determine whether the case is explicitly Capex."""
    request_type = _text(
        case_data.get("request_type")
    )

    return (
        "capital expenditure" in request_type
        or "capex" in request_type
        or "capital expenditure" in case_text
        or "capex" in case_text
    )


def _is_procurement_case(case_data, case_text):
    """Determine whether the case is procurement-related."""
    request_type = _text(
        case_data.get("request_type")
    )

    return (
        "procurement" in request_type
        or "purchase" in request_type
        or "procurement" in case_text
        or "purchase" in case_text
    )


def _is_specialized_procurement(case_data):
    """
    Identify case context where technical evaluation may be
    conditionally required by PEIS policy.
    """

    case_text = _case_text(case_data)

    specialized_terms = [
        "specialized equipment",
        "specialised equipment",
        "technical equipment",
        "technically complex",
        "technical procurement",
        "engineering equipment",
        "engineering service",
        "engineering services",
        "industrial equipment",
        "testing equipment",
        "laboratory equipment",
        "automation equipment",
        "control system",
        "technical system",
        "specialized system",
        "specialised system",
    ]

    return any(
        term in case_text
        for term in specialized_terms
    )


# ==========================================================
# POLICY RULE EXTRACTION
# ==========================================================

def _extract_quotation_rule(policy_text):
    """
    Extract the quotation rule established by retrieved policy.

    Returns:
        {
            "required": bool,
            "minimum_count": int | None,
            "threshold": float | None
        }

    The current PEIS policy states:
        Purchases > PKR 500,000 require at least
        3 vendor quotations unless an approved
        single-source justification applies.

    This function intentionally does not invent a quotation
    requirement when the retrieved policy does not establish one.
    """

    quotation_rule_exists = _has_policy_phrase(
        policy_text,
        [
            "three vendor quotations",
            "at least three vendor quotations",
            "3 vendor quotations",
            "three quotations",
            "at least 3 quotations",
        ],
    )

    if not quotation_rule_exists:
        return {
            "required": False,
            "minimum_count": None,
            "threshold": None,
        }

    # ------------------------------------------------------
    # Determine quotation count from policy wording
    # ------------------------------------------------------

    minimum_count = None

    count_patterns = [
        r"at least\s+(\d+)\s+(?:vendor\s+)?quotations?",
        r"(\d+)\s+(?:vendor\s+)?quotations?",
    ]

    for pattern in count_patterns:

        match = re.search(
            pattern,
            policy_text,
            flags=re.IGNORECASE,
        )

        if match:

            try:
                candidate = int(
                    match.group(1)
                )

                if candidate > 0:
                    minimum_count = candidate
                    break

            except ValueError:
                pass

    # Current PEIS policy explicitly establishes three.
    if minimum_count is None:
        if (
            "three vendor quotations" in policy_text
            or "three quotations" in policy_text
        ):
            minimum_count = 3

    if minimum_count is None:
        return {
            "required": False,
            "minimum_count": None,
            "threshold": None,
        }

    # ------------------------------------------------------
    # Extract threshold associated with quotation rule
    # ------------------------------------------------------

    threshold = None

    threshold_patterns = [
        r"(?:above|over|exceeding)\s+pk?r?\s*([0-9][0-9,]*)",
        r"pk?r?\s*([0-9][0-9,]*)\s*(?:and above|or above)",
        r"purchases?\s+(?:above|over|exceeding)\s+([0-9][0-9,]*)",
    ]

    for pattern in threshold_patterns:

        match = re.search(
            pattern,
            policy_text,
            flags=re.IGNORECASE,
        )

        if match:

            try:
                threshold = float(
                    match.group(1).replace(",", "")
                )
                break

            except ValueError:
                pass

    return {
        "required": True,
        "minimum_count": minimum_count,
        "threshold": threshold,
    }


# ==========================================================
# SINGLE-SOURCE EXCEPTION
# ==========================================================

def _single_source_exception_documented(
    documents,
    case_text,
):
    """
    Determine whether there is explicit evidence of a documented
    and approved single-source exception.

    Merely mentioning "single source" is NOT sufficient.

    This function looks for:
        - explicit single-source terminology
        - AND justification/approval evidence

    This is evidence detection only. It does not independently
    determine whether the exception is substantively valid.
    """

    combined_text = case_text

    for document in documents:
        combined_text += " " + _document_text(document)

    # ------------------------------------------------------
    # Explicit single-source terminology
    # ------------------------------------------------------

    single_source_terms = [
        "single source",
        "single-source",
        "sole source",
        "sole-source",
        "single vendor",
        "single-vendor",
    ]

    has_single_source_term = any(
        term in combined_text
        for term in single_source_terms
    )

    if not has_single_source_term:
        return False

    # ------------------------------------------------------
    # Explicit justification / exception evidence
    # ------------------------------------------------------

    justification_terms = [
        "single source justification",
        "single-source justification",
        "sole source justification",
        "sole-source justification",
        "single source exception",
        "single-source exception",
        "sole source exception",
        "sole-source exception",
        "exception justification",
    ]

    has_justification = any(
        term in combined_text
        for term in justification_terms
    )

    # ------------------------------------------------------
    # Explicit approval evidence
    # ------------------------------------------------------

    approval_terms = [
        "approved single source",
        "approved single-source",
        "approved sole source",
        "approved sole-source",
        "single source approved",
        "single-source approved",
        "sole source approved",
        "sole-source approved",
        "exception approved",
        "exception approval",
        "approval for single source",
        "approval for single-source",
    ]

    has_approval = any(
        term in combined_text
        for term in approval_terms
    )

    # A documented justification is sufficient to create the
    # Single-Source Justification requirement. However, it should
    # not by itself be treated as proof of an approved exception.
    #
    # Therefore this function is deliberately strict: it returns
    # True only where the supplied evidence contains both explicit
    # single-source language and justification/approval language.

    return (
        has_single_source_term
        and has_justification
        and has_approval
    )


# ==========================================================
# FINANCIAL REVIEW EVIDENCE
# ==========================================================

def _has_financial_review_evidence(documents):
    """
    Determine whether uploaded documents explicitly demonstrate
    financial review.

    AI-generated analysis does NOT count as evidence.
    """

    financial_phrases = [
        "financial review",
        "finance review",
        "reviewed by finance",
        "reviewed by finance department",
        "finance department review",
        "financially reviewed",
        "financial approval",
        "finance approval",
        "reviewed by finance manager",
        "reviewed by finance department",
    ]

    for document in documents:

        text = _document_text(document)

        if any(
            phrase in text
            for phrase in financial_phrases
        ):
            return True

    return False


# ==========================================================
# REQUIREMENT CREATION
# ==========================================================

def _make_requirement(
    requirement_id,
    name,
    document_type=None,
    mandatory=True,
    reason="",
    status="MISSING",
    minimum_count=None,
    evidence_rule=None,
):
    """Create a consistent requirement object."""

    requirement = {
        "id": requirement_id,
        "name": name,
        "document_type": document_type,
        "mandatory": mandatory,
        "reason": reason,
        "status": status,
    }

    if minimum_count is not None:
        requirement["minimum_count"] = minimum_count

    if evidence_rule:
        requirement["evidence_rule"] = evidence_rule

    return requirement


# ==========================================================
# MAIN REQUIREMENT ENGINE
# ==========================================================

def determine_requirements(
    case_data,
    documents,
    policy_evidence,
):
    """
    Determine mandatory evidence requirements from applicable
    PEIS policy and case context.

    No universal checklist is imposed.
    """

    case_data = case_data or {}
    documents = documents or []
    policy_evidence = policy_evidence or []

    if not policy_evidence:
        return [
            _make_requirement(
                requirement_id="applicable_policy_evidence",
                name="Applicable Policy Evidence",
                document_type=None,
                mandatory=True,
                reason=(
                    "AegisAI could not retrieve applicable policy "
                    "evidence for this case. The Evidence Gate cannot "
                    "be completed until applicable policy evidence is "
                    "available."
                ),
                status="MISSING",
                evidence_rule="RAG policy retrieval required",
            )
        ]

    amount = _amount(case_data)

    case_text = _case_text(
        case_data
    )

    policy_text = _all_policy_text(
        policy_evidence
    )

    requirements = []

    capital_expenditure = _is_capital_expenditure(
        case_data,
        case_text,
    )

    procurement_case = _is_procurement_case(
        case_data,
        case_text,
    )

    # ======================================================
    # PURCHASE REQUEST
    # ======================================================

    if (
        _has_policy_phrase(
            policy_text,
            [
                "purchase request",
                "purchase requisition",
            ],
        )
        and (capital_expenditure or procurement_case)
    ):

        requirements.append(
            _make_requirement(
                requirement_id="purchase_request",
                name="Purchase Request",
                document_type="Purchase Request",
                mandatory=True,
                reason=(
                    "Applicable PEIS procurement procedure "
                    "requires a Purchase Request."
                ),
                status=(
                    "COMPLETE"
                    if _has_document_type(
                        documents,
                        "Purchase Request",
                    )
                    else "MISSING"
                ),
                evidence_rule="POL-004 / SOP-01",
            )
        )

    # ======================================================
    # BUSINESS JUSTIFICATION
    # ======================================================

    if (
        _has_policy_phrase(
            policy_text,
            [
                "business justification",
                "business need",
            ],
        )
        and (capital_expenditure or procurement_case)
    ):

        requirements.append(
            _make_requirement(
                requirement_id="business_justification",
                name="Business Justification",
                document_type="Business Justification",
                mandatory=True,
                reason=(
                    "Applicable PEIS policy requires the "
                    "business need/justification to be documented."
                ),
                status=(
                    "COMPLETE"
                    if _has_document_type(
                        documents,
                        "Business Justification",
                    )
                    else "MISSING"
                ),
                evidence_rule="POL-004 / SOP-02",
            )
        )

    # ======================================================
    # QUOTATION REQUIREMENT
    # ======================================================

    quotation_rule = _extract_quotation_rule(
        policy_text
    )

    quotation_threshold_applies = (
        quotation_rule["required"]
        and (
            quotation_rule["threshold"] is None
            or amount > quotation_rule["threshold"]
        )
    )

    if quotation_threshold_applies:

        minimum_count = (
            quotation_rule["minimum_count"]
            or 1
        )

        # --------------------------------------------------
        # Determine whether an approved exception is
        # actually documented.
        # --------------------------------------------------

        approved_single_source = (
            _single_source_exception_documented(
                documents,
                case_text,
            )
        )

        if approved_single_source:

            # ----------------------------------------------
            # Single-source route
            # ----------------------------------------------

            requirements.append(
                _make_requirement(
                    requirement_id="single_source_justification",
                    name="Single-Source Justification",
                    document_type="Single-Source Justification",
                    mandatory=True,
                    reason=(
                        "The supplied evidence indicates an "
                        "approved single-source exception. "
                        "The exception must be supported by "
                        "documented justification."
                    ),
                    status=(
                        "COMPLETE"
                        if (
                            _has_document_type(
                                documents,
                                "Single-Source Justification",
                            )
                            or any(
                                (
                                    "single source justification"
                                    in _document_text(document)
                                    or
                                    "single-source justification"
                                    in _document_text(document)
                                )
                                for document in documents
                            )
                        )
                        else "MISSING"
                    ),
                    evidence_rule=(
                        "PEIS quotation exception route"
                    ),
                )
            )

        else:

            # ----------------------------------------------
            # Competitive procurement
            # ----------------------------------------------

            quotation_count = _document_count(
                documents,
                "Vendor Quotation",
            )

            quotation_name = (
                f"{minimum_count} Vendor Quotations"
                if minimum_count > 1
                else "Vendor Quotation"
            )

            requirements.append(
                _make_requirement(
                    requirement_id="vendor_quotations",
                    name=quotation_name,
                    document_type="Vendor Quotation",
                    mandatory=True,
                    minimum_count=minimum_count,
                    reason=(
                        "Applicable PEIS policy requires at "
                        f"least {minimum_count} vendor "
                        "quotation"
                        + (
                            "s."
                            if minimum_count != 1
                            else "."
                        )
                    ),
                    status=(
                        "COMPLETE"
                        if quotation_count >= minimum_count
                        else "MISSING"
                    ),
                    evidence_rule=(
                        "Policy-derived quotation requirement"
                    ),
                )
            )

            # ----------------------------------------------
            # Comparative Statement
            # ----------------------------------------------

            if _has_policy_phrase(
                policy_text,
                [
                    "comparative statement",
                    "comparative analysis",
                ],
            ):

                requirements.append(
                    _make_requirement(
                        requirement_id="comparative_statement",
                        name="Comparative Statement",
                        document_type="Comparative Statement",
                        mandatory=True,
                        reason=(
                            "Applicable PEIS procurement "
                            "procedure requires a Comparative "
                            "Statement for competitive "
                            "procurement."
                        ),
                        status=(
                            "COMPLETE"
                            if _has_document_type(
                                documents,
                                "Comparative Statement",
                            )
                            else "MISSING"
                        ),
                        evidence_rule=(
                            "POL-001 / P-04; POL-004 / SOP-05"
                        ),
                    )
                )

    # ======================================================
    # TECHNICAL EVALUATION
    # ======================================================

    if (
        _has_policy_phrase(
            policy_text,
            [
                "technical evaluation",
                "specialized equipment",
                "technically complex",
            ],
        )
        and _is_specialized_procurement(
            case_data
        )
    ):

        requirements.append(
            _make_requirement(
                requirement_id="technical_evaluation",
                name="Technical Evaluation",
                document_type="Technical Evaluation",
                mandatory=True,
                reason=(
                    "Applicable PEIS policy requires technical "
                    "evaluation for specialized equipment, "
                    "engineering services, or technically "
                    "complex procurement."
                ),
                status=(
                    "COMPLETE"
                    if _has_document_type(
                        documents,
                        "Technical Evaluation",
                    )
                    else "MISSING"
                ),
                evidence_rule=(
                    "POL-001 / P-03; POL-004 / SOP-04"
                ),
            )
        )

    # ======================================================
    # FINANCIAL REVIEW
    # ======================================================

    if _has_policy_phrase(
        policy_text,
        [
            "financial review before approval",
            "financial review",
        ],
    ):

        requirements.append(
            _make_requirement(
                requirement_id="financial_review",
                name="Financial Review",
                document_type=None,
                mandatory=True,
                reason=(
                    "Applicable PEIS policy requires financial "
                    "review before approval."
                ),
                status=(
                    "COMPLETE"
                    if _has_financial_review_evidence(
                        documents
                    )
                    else "MISSING"
                ),
                evidence_rule="POL-004 / SOP-06",
            )
        )

    # ======================================================
    # REQUIRED APPROVAL
    # ======================================================

    if (
        _has_policy_phrase(
            policy_text,
            [
                "required approval",
                "approval before po",
                "approval before purchase order",
                "approval authority",
                "delegation of authority",
            ],
        )
        and amount > 0
    ):

        requirements.append(
            _make_requirement(
                requirement_id="approval_request",
                name="Required Approval",
                document_type="Approval Request",
                mandatory=True,
                reason=(
                    "Applicable PEIS policy requires approval "
                    "by the authority applicable to the request "
                    "amount before the PO/approval is issued."
                ),
                status=(
                    "COMPLETE"
                    if _has_document_type(
                        documents,
                        "Approval Request",
                    )
                    else "MISSING"
                ),
                evidence_rule=(
                    "POL-003 / DA; POL-004 / SOP-07"
                ),
            )
        )

    # ======================================================
    # REMOVE DUPLICATES
    # ======================================================

    unique_requirements = {}

    for requirement in requirements:

        requirement_id = requirement.get("id")

        if requirement_id:
            unique_requirements[
                requirement_id
            ] = requirement

    return list(
        unique_requirements.values()
    )


# ==========================================================
# MISSING REQUIREMENTS
# ==========================================================

def get_missing_requirements(requirements):
    """Return mandatory requirements that are incomplete."""

    missing = []

    for requirement in requirements or []:

        if not requirement.get(
            "mandatory",
            False,
        ):
            continue

        if requirement.get(
            "status"
        ) != "COMPLETE":

            missing.append(
                requirement
            )

    return missing


# ==========================================================
# EVIDENCE GATE
# ==========================================================

def evidence_gate(requirements):
    """
    Evaluate whether all mandatory policy-derived evidence
    requirements are complete.

    Returns JSON-serializable data suitable for Supabase JSONB.
    """

    requirements = requirements or []

    mandatory_requirements = [
        requirement
        for requirement in requirements
        if requirement.get(
            "mandatory",
            False,
        )
    ]

    missing = get_missing_requirements(
        requirements
    )

    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "missing_count": len(missing),
        "total_requirements": len(
            mandatory_requirements
        ),
    }
