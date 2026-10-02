from agents.compliance_agent import run_compliance_agent
from agents.financial_agent import run_financial_agent
from agents.risk_agent import run_risk_agent
from agents.decision_synthesizer import run_decision_synthesizer

from rag.retriever import search_policies

from services.evidence_requirements import (
    determine_requirements,
    evidence_gate,
)


def run_ai_case_review(case_data, documents):

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

    policy_evidence = search_policies(
        query,
        top_k=10
    )

    requirements = determine_requirements(
        case_data,
        documents,
        policy_evidence
    )

    gate = evidence_gate(
        requirements
    )

    compliance = run_compliance_agent(
        case_data,
        documents,
        policy_evidence
    )

    financial = run_financial_agent(
        case_data,
        documents,
        policy_evidence
    )

    risk = run_risk_agent(
        case_data,
        documents,
        policy_evidence
    )

    synthesis = run_decision_synthesizer(
        case_data,
        compliance,
        financial,
        risk
    )

    return {
        "policy_evidence": policy_evidence,
        "requirements": requirements,
        "evidence_gate": gate,
        "compliance": compliance,
        "financial": financial,
        "risk": risk,
        "synthesis": synthesis,
    }
