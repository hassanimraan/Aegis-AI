from google import genai

from config.settings import get_gemini_api_key


MODEL = "gemini-3.6-flash"


def run_compliance_agent(
    case_data,
    documents,
    policy_evidence
):
    client = genai.Client(
        api_key=get_gemini_api_key()
    )

    document_text = "\n\n".join(
        [
            f"DOCUMENT: {doc['document_name']}\n"
            f"TYPE: {doc['document_type']}\n"
            f"CONTENT:\n{doc['extracted_text']}"
            for doc in documents
        ]
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

    prompt = f"""
You are the Compliance Agent in AegisAI,
an AI-powered procurement approval system.

Your task is to review an approval case against
the supplied PEIS procurement policies and documents.

IMPORTANT RULES:
- Use ONLY the supplied policy evidence.
- Use ONLY the supplied case and document information.
- Do not invent policies, requirements, documents, or facts.
- Clearly identify missing documents or information.
- Distinguish between PASS and ATTENTION.
- Cite the relevant policy ID and section ID.
- If the evidence is insufficient, say so.
- Do not infer an approval authority from incomplete threshold evidence.
- Do not extrapolate missing approval thresholds.
- If the exact approval authority cannot be established from the supplied
  policy evidence, state that it cannot be determined from the available
  evidence.
- Exact financial thresholds and approval authority will be assessed by
  the Financial Agent.
- Do not make the final human approval decision.

CASE INFORMATION:
Title: {case_data.get("title", "")}
Department: {case_data.get("department", "")}
Amount: {case_data.get("amount", "")}
Description: {case_data.get("description", "")}

SUPPLIED DOCUMENTS:
{document_text}

RELEVANT POLICY EVIDENCE:
{policy_text}

Return your assessment using exactly this structure:

COMPLIANCE RESULT:
PASS or ATTENTION

SUMMARY:
Brief overall compliance assessment.

REQUIREMENTS CHECK:
- Requirement:
- Evidence:
- Status:
- Policy:

For approval-authority-related requirements, do not determine the exact
approval authority. State that approval authority assessment is deferred
to the Financial Agent unless the supplied policy evidence explicitly
establishes the authority.

MISSING OR UNCLEAR ITEMS:
List missing or unclear requirements.
Write "None identified" if there are none.

POLICY EVIDENCE:
List the policy sections used.

RECOMMENDATION:
State whether the case appears compliant from a compliance/documentation perspective,
or requires clarification/escalation.

Do not provide a final human approval decision.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    return response.text
