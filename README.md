````markdown
# AegisAI

### AI-Powered Approval & Compliance System

**AegisAI** is an AI-powered approval and compliance system that uses **Retrieval-Augmented Generation (RAG), multi-agent AI, policy intelligence, and human-in-the-loop decision-making** to support procurement and capital expenditure reviews.

> **AegisAI = AI that acts as a protective shield for business decisions.**

---

## 🎯 Purpose

AegisAI helps organizations review approval cases against applicable policies, required evidence, financial controls, procurement requirements, and risk considerations before a human reviewer makes the final decision.

The system is designed to make AI-assisted approval workflows:

- Policy-grounded
- Evidence-driven
- Transparent
- Auditable
- Human-controlled

AI recommendations are advisory. **The final approval decision always remains with the human reviewer.**

---

## 🔄 Core Workflow

```text
User Login
    ↓
Dashboard
    ↓
Create Case
    ↓
Upload Available Documents
    ↓
AI Case Review
    ↓
Determine Applicable Policies
    ↓
RAG Policy Evidence Retrieval
    ↓
Policy-Driven Evidence Requirements
    ↓
Evidence Gate
    ↓
┌───────────────────────────────┐
│ Missing Mandatory Evidence?   │
└───────────────┬───────────────┘
                │
        Yes ────┴──── Upload Missing Evidence
                │
                └──── Run AI Review Again

                ↓ Complete

Compliance Agent
    ↓
Financial Agent
    ↓
Risk Agent
    ↓
Decision Synthesizer
    ↓
Human Review
    ↓
Grounded Q&A
    ↓
Approve / Return / Reject
    ↓
Audit Trail
    ↓
Case History & Report
````

---

## 🤖 Multi-Agent AI

AegisAI uses specialized AI agents for different aspects of an approval case.

### Compliance Agent

Reviews:

* Procurement requirements
* Required documentation
* Policy compliance
* Procurement procedures
* Conflict-of-interest requirements

### Financial Agent

Reviews:

* Financial information
* Amount consistency
* Financial review evidence
* Approval authority
* Delegation-of-authority requirements

### Risk Agent

Reviews:

* Documentation risks
* Vendor risks
* Process risks
* Technical/commercial risks
* Governance risks
* Conflict-of-interest indicators

### Decision Synthesizer

Consolidates the available agent findings into an overall assessment and advisory recommendation.

The synthesizer does not replace the human decision-maker.

---

## 📚 Policy Intelligence & RAG

AegisAI uses Retrieval-Augmented Generation to retrieve relevant policy sections from the PEIS policy knowledge base.

The system:

1. Converts the case question into an embedding.
2. Searches the policy knowledge base.
3. Retrieves relevant policy sections.
4. Provides the retrieved evidence to the AI agents.
5. Uses policy evidence to determine applicable requirements.

Policy references are retained using identifiers such as:

```text
POL-001 P-02
POL-003 DA-03
POL-004 SOP-09
```

This helps keep AI responses grounded in the supplied policy framework.

---

## 🔐 Policy-Driven Evidence Gate

AegisAI does not assume that every case requires the same documents.

Evidence requirements are determined from:

* Applicable policies
* Case characteristics
* Procurement type
* Financial thresholds
* Required approvals
* Conditional requirements
* Documented exceptions

For example, where the applicable policy requires three vendor quotations, the Evidence Gate requires the corresponding evidence.

Where an approved single-source exception applies, the system can require the relevant single-source justification instead.

### Human Decision Protection

If mandatory policy-required evidence is incomplete:

```text
FINAL DECISION LOCKED
```

The human reviewer cannot submit Approve / Return / Reject until the required evidence is available and the AI review has been run again.

---

## 👤 Human-in-the-Loop

AegisAI intentionally keeps the final decision with a human reviewer.

The reviewer can:

* Review the AI assessment
* Examine policy evidence
* Ask grounded questions
* Review supplied documents
* See missing evidence
* Approve
* Return for clarification
* Reject

The system records the final human decision separately from the AI recommendation.

---

## 💬 Grounded Review Assistant

The Human Review page includes a grounded Q&A assistant.

Questions are answered using:

* Case information
* Supplied case documents
* Retrieved policy evidence
* Completed AI review

The assistant is instructed not to invent policies, documents, approvals, financial reviews, or facts that are not supported by the available evidence.

---

## 🧾 Audit Trail

AegisAI records important workflow actions including human decisions.

Audit information supports traceability of:

* Case activity
* Human decisions
* Decision comments
* Case status changes
* Review history

---

## 📊 Case Management

The application provides:

* Dashboard
* Case creation
* Document management
* AI case review
* Human decision
* Case history
* Reports

Case status can include:

```text
DRAFT
APPROVED
RETURNED
REJECTED
```

---

## 📄 Reports

AegisAI can generate a PDF report containing relevant case information, AI assessment, human decision information, and audit history.

The report also clearly identifies the AI assessment as advisory.

---

## 🏗️ Technology Stack

| Component            | Technology                            |
| -------------------- | ------------------------------------- |
| Frontend             | Streamlit                             |
| Programming Language | Python                                |
| AI                   | Google Gemini                         |
| RAG                  | Gemini Embeddings + Cosine Similarity |
| Database             | Supabase                              |
| Authentication       | Supabase Auth                         |
| Document Processing  | Python / pypdf                        |
| Data Processing      | Pandas / NumPy                        |
| PDF Reports          | ReportLab                             |
| Deployment           | Streamlit Cloud                       |
| Source Control       | GitHub                                |

---

## 📁 Project Structure

```text
AegisAI/
├── agents/
│   ├── compliance_agent.py
│   ├── decision_synthesizer.py
│   ├── financial_agent.py
│   └── risk_agent.py
│
├── config/
│   └── settings.py
│
├── database/
│   └── supabase_client.py
│
├── knowledge_base/
│   └── policy_embeddings.json
│
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Create_Case.py
│   ├── 4_Decision.py
│   ├── 5_Case_History.py
│   └── 6_Report.py
│
├── rag/
│   ├── knowledge_base.py
│   └── retriever.py
│
├── services/
│   ├── authentication.py
│   ├── ai_review.py
│   └── evidence_requirements.py
│
├── app.py
├── readme.md
└── requirements.txt
```

---

## 🔑 Configuration

AegisAI requires the following secrets:

```text
SUPABASE_URL
SUPABASE_KEY
GEMINI_API_KEY
```

These should be configured through the deployment platform's secret-management system.

Credentials should **not** be committed to the repository.

---

## 🚀 Running the Application

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Run Streamlit:

```bash
streamlit run app.py
```

---

## 🧠 Design Principles

AegisAI follows several core principles:

### 1. Policy Grounding

AI reasoning should be based on the supplied policy evidence rather than invented requirements.

### 2. Evidence Before Decision

Mandatory policy-required evidence must be available before the final human decision can be submitted.

### 3. Human Authority

AI provides recommendations and analysis. The human reviewer makes the final decision.

### 4. Transparency

AI findings, policy references, missing evidence, human decisions, and audit information remain visible to the reviewer.

### 5. No Unsupported Assumptions

Missing information is treated as missing information rather than automatically being interpreted as misconduct or non-compliance.

---

## 🏆 Hackathon MVP

AegisAI was developed as an MVP for demonstrating how **Generative AI, Agentic AI, RAG, policy intelligence, and human-in-the-loop governance** can be combined into an approval and compliance workflow.

The MVP focuses on demonstrating the complete decision-support lifecycle rather than enterprise-scale infrastructure.

---

## ⚠️ Important

AegisAI is a decision-support system.

**AI-generated assessments and recommendations are advisory and must be reviewed by an authorized human decision-maker before any organizational action is taken.**

```

After replacing it, **`readme.md` will be FINAL / LOCKED ✅**.

Then we will do the **last full-system audit** rather than continuing file-by-file indefinitely: imports → database/schema → RAG → Evidence Gate → AI agents → human decision → reports → secrets → deployment → final demo workflow.
```
