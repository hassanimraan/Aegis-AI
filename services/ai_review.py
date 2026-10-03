from datetime import datetime, timezone

from agents.compliance_agent import run_compliance_agent
from agents.financial_agent import run_financial_agent
from agents.risk_agent import run_risk_agent
from agents.decision_synthesizer import run_decision_synthesizer

from rag.retriever import search_policies

from services.evidence_requirements import (
    determine_requirements,
    evidence_gate,
)

from database.supabase_client import get_supabase


STEP_RAG = "RAG"
STEP_COMPLIANCE = "COMPLIANCE"
STEP_FINANCIAL = "FINANCIAL"
STEP_RISK = "RISK"
STEP_SYNTHESIS = "SYNTHESIS"
STEP_EVIDENCE = "EVIDENCE"

STEPS = [
    (STEP_RAG, 1),
    (STEP_COMPLIANCE, 2),
    (STEP_FINANCIAL, 3),
    (STEP_RISK, 4),
    (STEP_SYNTHESIS, 5),
    (STEP_EVIDENCE, 6),
]


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _get_step(case_id, step_name):
    supabase = get_supabase()

    response = (
        supabase
        .table("ai_review_steps")
        .select("*")
        .eq("case_id", case_id)
        .eq("step_name", step_name)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def _save_step(
    case_id,
    step_name,
    step_order,
    status,
    provider=None,
    model=None,
    result=None,
    error=None,
    started_at=None,
    completed_at=None,
):
    supabase = get_supabase()

    payload = {
        "case_id": case_id,
        "step_name": step_name,
        "step_order": step_order,
        "status": status,
        "provider": provider,
        "model": model,
        "result": result,
        "error": error,
        "started_at": started_at,
        "completed_at": completed_at,
        "updated_at": _utc_now(),
    }

    (
        supabase
        .table("ai_review_steps")
        .upsert(
            payload,
            on_conflict="case_id,step_name"
        )
        .execute()
    )


def _clear_steps(case_id):
    supabase = get_supabase()

    (
        supabase
        .table("ai_review_steps")
        .delete()
        .eq("case_id", case_id)
        .execute()
    )


def _start_step(case_id, step_name, step_order):
    started_at = _utc_now()

    _save_step(
        case_id=case_id,
        step_name=step_name,
        step_order=step_order,
        status="RUNNING",
        started_at=started_at,
    )

    return started_at


def _complete_step(
    case_id,
    step_name,
    step_order,
    result,
    provider=None,
    model=None,
    started_at=None,
):
    _save_step(
        case_id=case_id,
        step_name=step_name,
        step_order=step_order,
        status="COMPLETED",
        provider=provider,
        model=model,
        result=result,
        started_at=started_at,
        completed_at=_utc_now(),
    )


def _fail_step(
    case_id,
    step_name,
    step_order,
    error,
    started_at=None,
):
    _save_step(
        case_id=case_id,
        step_name=step_name,
        step_order=step_order,
        status="FAILED",
        error=str(error),
        started_at=started_at,
        completed_at=_utc_now(),
    )


def _extract_llm_text(result):
    if isinstance(result, dict):
        return result.get("text", "")

    if result is None:
        return ""

    return str(result)


def _extract_llm_metadata(result):
    if not isinstance(result, dict):
        return None, None

    return (
        result.get("provider"),
        result.get("model"),
    )


def _run_or_resume_step(
    case_id,
    step_name,
    step_order,
    function,
):
    existing = _get_step(case_id, step_name)

    if existing and existing.get("status") == "COMPLETED":
        return existing.get("result")

    started_at = _start_step(
        case_id,
        step_name,
        step_order,
    )

    try:
        result = function()

        provider, model = _extract_llm_metadata(result)

        _complete_step(
            case_id=case_id,
            step_name=step_name,
            step_order=step_order,
            result=result,
            provider=provider,
            model=model,
            started_at=started_at,
        )

        return result

    except Exception as error:
        _fail_step(
            case_id=case_id,
            step_name=step_name,
            step_order=step_order,
            error=error,
            started_at=started_at,
        )

        raise


def run_ai_case_review(
    case_data,
    documents,
    force_restart=False,
):
    case_id = case_data.get("id")

    if not case_id:
        raise ValueError(
            "Case ID is required to run the AI case review."
        )

    if force_restart:
        _clear_steps(case_id)

        supabase = get_supabase()

        (
            supabase
            .table("ai_reviews")
            .delete()
            .eq("case_id", case_id)
            .execute()
        )

    query = f"""
    Procurement approval case.

    Title:
    {case_data.get("title", "")}

    Department:
    {case_data.get("department", "")}

    Amount:
    {case_data.get("amount", "")}

    Description:
    {case_data.get("description", "")}

    Identify the PEIS policy sections applicable
    to this case, including procurement, financial approval,
    delegation of authority, technical evaluation,
    quotations, comparative statement, financial review,
    vendor evaluation, and conflict of interest where relevant.
    """

    # ---------------------------------------------------------
    # STEP 1 — RAG POLICY RETRIEVAL
    # ---------------------------------------------------------

    rag_step = _get_step(case_id, STEP_RAG)

    if rag_step and rag_step.get("status") == "COMPLETED":
        rag_result = rag_step.get("result") or {}

        policy_evidence = rag_result.get(
            "policy_evidence",
            []
        )

        requirements = rag_result.get(
            "requirements",
            []
        )

    else:
        started_at = _start_step(
            case_id,
            STEP_RAG,
            1,
        )

        try:
            policy_evidence = search_policies(
                query,
                top_k=10,
            )

            requirements = determine_requirements(
                case_data,
                documents,
                policy_evidence,
            )

            rag_result = {
                "policy_evidence": policy_evidence,
                "requirements": requirements,
            }

            _complete_step(
                case_id=case_id,
                step_name=STEP_RAG,
                step_order=1,
                result=rag_result,
                provider="gemini-embedding",
                model="gemini-embedding-001",
                started_at=started_at,
            )

        except Exception as error:
            _fail_step(
                case_id=case_id,
                step_name=STEP_RAG,
                step_order=1,
                error=error,
                started_at=started_at,
            )

            raise

    # ---------------------------------------------------------
    # STEP 2 — COMPLIANCE AGENT
    # ---------------------------------------------------------

    compliance = _run_or_resume_step(
        case_id=case_id,
        step_name=STEP_COMPLIANCE,
        step_order=2,
        function=lambda: run_compliance_agent(
            case_data,
            documents,
            policy_evidence,
        ),
    )

    compliance_text = _extract_llm_text(compliance)

    # ---------------------------------------------------------
    # STEP 3 — FINANCIAL AGENT
    # ---------------------------------------------------------

    financial = _run_or_resume_step(
        case_id=case_id,
        step_name=STEP_FINANCIAL,
        step_order=3,
        function=lambda: run_financial_agent(
            case_data,
            documents,
            policy_evidence,
        ),
    )

    financial_text = _extract_llm_text(financial)

    # ---------------------------------------------------------
    # STEP 4 — RISK AGENT
    # ---------------------------------------------------------

    risk = _run_or_resume_step(
        case_id=case_id,
        step_name=STEP_RISK,
        step_order=4,
        function=lambda: run_risk_agent(
            case_data,
            documents,
            policy_evidence,
        ),
    )

    risk_text = _extract_llm_text(risk)

    # ---------------------------------------------------------
    # STEP 5 — DECISION SYNTHESIZER
    # ---------------------------------------------------------

    synthesis = _run_or_resume_step(
        case_id=case_id,
        step_name=STEP_SYNTHESIS,
        step_order=5,
        function=lambda: run_decision_synthesizer(
            case_data,
            compliance_text,
            financial_text,
            risk_text,
        ),
    )

    # ---------------------------------------------------------
    # STEP 6 — EVIDENCE GATE
    # ---------------------------------------------------------

    evidence_step = _get_step(
        case_id,
        STEP_EVIDENCE,
    )

    if (
        evidence_step
        and evidence_step.get("status") == "COMPLETED"
    ):
        evidence_result = evidence_step.get("result") or {}

        requirements = evidence_result.get(
            "requirements",
            requirements,
        )

        gate = evidence_result.get(
            "evidence_gate",
            {},
        )

    else:
        started_at = _start_step(
            case_id,
            STEP_EVIDENCE,
            6,
        )

        try:
            requirements = determine_requirements(
                case_data,
                documents,
                policy_evidence,
            )

            gate = evidence_gate(
                requirements,
            )

            evidence_result = {
                "requirements": requirements,
                "evidence_gate": gate,
            }

            _complete_step(
                case_id=case_id,
                step_name=STEP_EVIDENCE,
                step_order=6,
                result=evidence_result,
                provider="rule-engine",
                model=None,
                started_at=started_at,
            )

        except Exception as error:
            _fail_step(
                case_id=case_id,
                step_name=STEP_EVIDENCE,
                step_order=6,
                error=error,
                started_at=started_at,
            )

            raise

    # ---------------------------------------------------------
    # FINAL RESULT
    # ---------------------------------------------------------

    return {
        "policy_evidence": policy_evidence,
        "requirements": requirements,
        "evidence_gate": gate,
        "compliance": compliance,
        "financial": financial,
        "risk": risk,
        "synthesis": synthesis,
    }
