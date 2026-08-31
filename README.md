# SupportPilot AI

> **Multi-tool AI customer-support resolution agent built with Gemini tool calling, FastAPI, PostgreSQL, pgvector, structured resolution logic, persistent conversations, agent observability, and evidence-grounded responses.**

![Version](https://img.shields.io/badge/version-V2%20Multi--Tool%20Resolution-5B7CFA)
![Status](https://img.shields.io/badge/status-complete-brightgreen)
![Tests](https://img.shields.io/badge/tests-55%2F55%20passing-brightgreen)
![Live Evaluation](https://img.shields.io/badge/live%20Gemini-8%2F8%20passed-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791)
![Gemini](https://img.shields.io/badge/AI-Gemini-8E75FF)

**SupportPilot AI** is a local AI customer-support resolution agent built around a fictional SaaS platform called **CloudDesk**.

V1 established the agent foundation: tool calling, grounded retrieval, persistence, observability, and safety controls.

V2 turns that foundation into a **multi-tool resolution system** that can investigate one customer issue across multiple business systems, combine evidence, determine a structured outcome, preserve conversational context, restore conversations after browser refreshes, and expose a separate internal Agent Inspector for engineering visibility.

**Current release:** V2 — Multi-Tool Resolution & Customer Experience  
**Status:** ✅ Complete  
**Automated tests:** 55/55 passing  
**Live Gemini evaluation:** 8/8 scenarios passed  

---

## Customer Experience

The default interface is designed as a clean customer-support application rather than a developer dashboard.

Customers see only the information they need:

- support conversation
- customer ID
- current conversation state
- quick actions
- customer-friendly resolution status
- assistant responses
- message composer

Internal tool calls and execution traces are kept out of the normal customer experience.

![SupportPilot Customer UI](docs/V2/01_Customer_Landing.png)

---

## What V2 Demonstrates

SupportPilot V2 expands the V1 foundation with:

- Gemini-based multi-tool investigation
- Five approved read-only customer-support tools
- Dynamic sequential tool selection
- Cross-system evidence accumulation
- Payment-domain support
- Explicit structured resolution states
- Evidence-conflict handling
- Tool-failure guardrails
- Maximum investigation-step protection
- Duplicate-call protection
- Pydantic validation for tool arguments
- PostgreSQL persistence
- Semantic knowledge retrieval with Gemini embeddings + pgvector
- Browser conversation restoration
- Bounded recent conversational context
- Safe Markdown rendering
- Separate customer UI and Agent Inspector
- Persisted tool sequence, latency, resolution and traces
- 55 automated tests
- 8 live Gemini smoke scenarios

---

# How SupportPilot V2 Works

A customer request does not go directly from the LLM to an answer.

```text
Customer
   │
   ▼
SupportPilot Customer UI
   │
   ▼
FastAPI
   │
   ▼
Agent Orchestrator
   │
   ▼
Gemini
   │
   ├── Decide which approved tool is required
   │
   ▼
Tool 1
   │
   ▼
Structured Evidence
   │
   ▼
Gemini
   │
   ├── Is more evidence required?
   │         │
   │         ├── YES → Tool 2 / Tool 3
   │         │
   │         └── NO
   │
   ▼
Resolution Engine
   │
   ▼
Customer-Safe Response
```

Gemini's automatic function execution is intentionally not used as an opaque black box.

SupportPilot manages the tool loop explicitly so that tool selection, validated arguments, execution results, errors, latency, persistence, traces, and final resolution remain visible to the application.

---

# V2 Support Tools

V2 exposes exactly five approved read-only tools.

| Tool | Purpose |
|---|---|
| `get_customer()` | Retrieve customer identity and account status |
| `get_subscription()` | Retrieve current plan, requested plan, subscription status and sync state |
| `get_payment_status()` | Retrieve deterministic CloudDesk payment information |
| `get_service_status()` | Check active CloudDesk service incidents |
| `search_knowledge_base()` | Search documented CloudDesk support knowledge |

The model chooses tools based on the customer problem and the evidence returned during the investigation.

The orchestration is **not hardcoded** to always execute every tool.

---

# Flagship V2 Scenario

The main V2 scenario demonstrates cross-system investigation.

Customer:

```text
CUS-1007
```

Synthetic CloudDesk state:

```text
Customer Account       ACTIVE
Current Plan           BASIC
Requested Plan         PRO
Subscription Sync      FAILED
Payment                SUCCESS
Payment For            PRO
```

Customer asks:

```text
I paid for Pro, but my account still shows Basic. What happened?
```

SupportPilot investigates:

```text
Customer Request
      │
      ▼
get_subscription()
      │
      ▼
Current Plan: BASIC
Requested Plan: PRO
Sync Status: FAILED
      │
      ▼
get_payment_status()
      │
      ▼
Payment Status: SUCCESS
Payment Plan: PRO
      │
      ▼
Compare Evidence
      │
      ▼
Payment succeeded
but requested plan was not applied
      │
      ▼
ESCALATION_REQUIRED
```

![SupportPilot Flagship Escalation](docs/V2/02_Flagship_Escalation.png)

The customer-facing response explains what was verified without claiming that SupportPilot repaired or modified the subscription.

---

# Structured Resolution Layer

V2 introduces four explicit investigation outcomes.

## `RESOLVED`

The available evidence supports a reliable answer or confirmed resolution.

## `NEEDS_INFORMATION`

The investigation cannot proceed because required information is missing.

Example:

```text
Customer ID cannot be verified
→ NEEDS_INFORMATION
```

## `UNRESOLVED`

The investigation completed, but available evidence is insufficient to reach a reliable conclusion.

Examples:

```text
Payment still pending
→ UNRESOLVED
```

```text
Related documentation retrieved,
but it does not confirm the requested fact
→ UNRESOLVED
```

## `ESCALATION_REQUIRED`

The available evidence confirms a real issue that the V2 read-only agent cannot safely resolve itself.

Example:

```text
Payment          SUCCESS
Requested Plan   PRO
Current Plan     BASIC
Sync Status      FAILED

→ ESCALATION_REQUIRED
```

A structured resolution can contain:

```json
{
  "resolution_status": "ESCALATION_REQUIRED",
  "issue_type": "subscription_upgrade_failure",
  "summary": "Payment succeeded but the requested Pro plan was not applied.",
  "evidence": [
    "Current plan is Basic",
    "Requested plan is Pro",
    "Subscription synchronization failed",
    "Payment completed successfully"
  ]
}
```

The customer receives natural language instead of raw internal state.

---

# Agent Inspector

V2 separates the customer interface from internal engineering observability.

Customer application:

```text
/
```

Internal Agent Inspector:

```text
/debug
```

![SupportPilot Agent Inspector](docs/V2/03_Agent_Inspector_Flagship_Run.png)

The Agent Inspector exposes structured application-level information including:

- Run ID
- Conversation ID
- Customer ID
- Request message
- Detected intent
- Prompt version
- Tool execution sequence
- Tool arguments
- Tool results
- Tool status
- Per-tool latency
- Total agent latency
- Resolution status
- Issue type
- Resolution summary
- Structured trace
- Final customer response
- Errors where applicable

Private model chain-of-thought is **not** exposed.

---

# Semantic Knowledge Retrieval

SupportPilot's knowledge tool uses semantic retrieval rather than simple keyword matching.

```text
Customer Question
        │
        ▼
Gemini Embedding 2
        │
        ▼
768-Dimensional Query Vector
        │
        ▼
PostgreSQL + pgvector
        │
        ▼
Cosine Similarity Search
        │
        ▼
Relevant CloudDesk Passages
        │
        ▼
Grounded Answer
```

### Example — Refund Policy

Customer:

```text
What is CloudDesk's refund policy?
```

SupportPilot retrieves the relevant CloudDesk refund-policy passage and answers from that evidence.

![Knowledge-Grounded Refund Policy](docs/V2/04_Knowledge_Grounded_Refund_Policy.png)

### Semantic stack

| Component | Implementation |
|---|---|
| Embedding model | `gemini-embedding-2` |
| Vector dimensions | 768 |
| Vector storage | PostgreSQL + pgvector |
| Retrieval | Cosine similarity |
| Knowledge tool | `search_knowledge_base()` |

---

# Grounding & Hallucination Control

V2 carries forward and strengthens the grounding rules established in V1.

```text
Semantic similarity ≠ factual proof

Missing documentation ≠ evidence that something is false

NOT_FOUND / ERROR ≠ negative business fact

Conflicting system evidence must be investigated,
not guessed away.

A tool failure must never be presented
as successful issue resolution.
```

### Example — Unsupported Lifetime Plan Question

Customer:

```text
Does CloudDesk offer a lifetime subscription plan?
```

The knowledge base contains related subscription material, but none of it confirms whether a lifetime plan exists.

Correct behavior:

```text
The available CloudDesk documentation does not provide enough
information to confirm whether CloudDesk offers a lifetime
subscription plan.
```

Structured result:

```text
UNRESOLVED
knowledge_evidence_unavailable
```

Incorrect behavior would be:

```text
CloudDesk does not offer lifetime subscriptions.
```

The grounding principle remains:

```text
Missing evidence ≠ evidence that something is false
```

---

# Conversational Context & Restoration

V2 preserves customer conversations across browser refreshes.

```text
Conversation created
        │
        ▼
conversation_id saved locally
        │
        ▼
Messages persisted in PostgreSQL
        │
        ▼
Browser refresh
        │
        ▼
conversation_id recovered
        │
        ▼
Persisted messages loaded
        │
        ▼
Conversation restored
```

V2 also supplies a bounded set of recent persisted messages to the agent.

This allows follow-ups such as:

```text
User:
I paid for Pro, but my account still shows Basic.

Agent:
The payment succeeded, but the requested upgrade
was not applied because subscription synchronization failed.

User:
Why did it fail?
```

The second request can understand what **"it"** refers to without introducing a long-term memory architecture.

---

# Evidence Conflict Handling

V2 treats contradictory system states as evidence of a problem.

Example:

```text
Payment System
SUCCESS

Subscription System
Current Plan: BASIC
Requested Plan: PRO
Sync Status: FAILED
```

SupportPilot must **not** silently convert this into:

```text
Your Pro subscription is active.
```

Instead, the contradiction becomes part of the structured investigation and can produce:

```text
ESCALATION_REQUIRED
subscription_upgrade_failure
```

---

# Payment Domain

V2 introduces a synthetic CloudDesk payment system.

Payment records can contain:

```text
Payment ID
Customer ID
Transaction Reference
Plan
Amount
Currency
Payment Status
Payment Date
```

Supported deterministic statuses:

```text
SUCCESS
FAILED
PENDING
REFUNDED
```

Example scenarios include:

| Scenario | Expected behavior |
|---|---|
| Payment SUCCESS + upgrade applied | `RESOLVED` |
| Payment FAILED | Explain failed payment safely |
| Payment PENDING | Do not claim success or failure |
| Payment missing | `UNRESOLVED` |
| Payment SUCCESS + plan BASIC + sync FAILED | `ESCALATION_REQUIRED` |

---

# Technical Architecture

```text
app/
│
├── agent/
│   ├── orchestrator.py
│   ├── resolution.py
│   └── schemas.py
│
├── api/
│   ├── debug.py
│   ├── health.py
│   └── support.py
│
├── db/
│   ├── models.py
│   ├── schema.py
│   ├── seed.py
│   └── session.py
│
├── tools/
│   ├── customer.py
│   ├── subscription.py
│   ├── payment.py
│   ├── service_status.py
│   └── knowledge.py
│
├── templates/
│   ├── index.html
│   └── debug.html
│
├── static/
│   ├── app.js
│   ├── styles.css
│   ├── debug.js
│   └── debug.css
│
├── config.py
└── main.py
```

Additional project areas:

```text
knowledge_base/
└── Synthetic CloudDesk support documents

scripts/
├── bootstrap.py
├── embed_knowledge.py
├── manual_tool_check.py
└── check_structure.py

tests/
├── unit/
├── integration/
└── workflows/

docs/
├── V1/
└── V2/
```

---

# Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| Backend | FastAPI |
| Validation | Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Database Driver | psycopg |
| Vector Search | pgvector |
| LLM | Gemini |
| Chat model | `gemini-3.5-flash-lite` |
| Embeddings | `gemini-embedding-2` |
| Frontend | HTML, CSS, JavaScript |
| Testing | pytest |
| API Testing | FastAPI TestClient / httpx |
| Source Control | Git + GitHub |

---

# Data & Persistence

SupportPilot persists application and agent activity in PostgreSQL.

Core entities include:

```text
customers
subscriptions
payments
service_incidents
documents
document_chunks
conversations
messages
agent_runs
tool_executions
```

V2 also persists:

```text
resolution_status
issue_type
resolution_summary
final_response
trace_json
```

A typical multi-tool interaction leaves a persistent trail:

```text
Conversation
     │
     ▼
User Message
     │
     ▼
Agent Run
     │
     ├── Tool Execution 1
     ├── Tool Execution 2
     └── Tool Execution 3 if needed
     │
     ▼
Structured Resolution
     │
     ▼
Assistant Message
```

---

# Synthetic CloudDesk Environment

CloudDesk is a fictional SaaS environment created specifically for SupportPilot.

No real customer data is used.

Important deterministic V2 scenarios include:

| ID | Scenario |
|---|---|
| `CUS-1001` | Basic active subscription; failed Pro payment |
| `CUS-1002` | Pro active subscription; successful payment |
| `CUS-1003` | Suspended Pro customer |
| `CUS-1004` | Basic → Pro upgrade pending; payment pending |
| `CUS-1005` | Upgrade requested; sync failed; payment record missing |
| `CUS-1006` | Successful Pro upgrade |
| `CUS-1007` | Payment succeeded but Pro upgrade sync failed |
| `INC-2001` | Active SEV2 CloudDesk core incident in EU |

These deterministic states make testing and evaluation repeatable.

---

# Knowledge Base

The V2 knowledge base contains synthetic CloudDesk support documentation:

```text
payment_troubleshooting.md
refund_policy.md
service_status.md
subscription_changes.md
support_scope.md
```

These documents exist only for the fictional CloudDesk environment.

---

# API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Customer SupportPilot UI |
| `GET` | `/debug` | Internal Agent Inspector |
| `GET` | `/health` | Application/database/agent health |
| `POST` | `/api/v1/support/chat` | Process a customer support request |
| `GET` | `/api/v1/support/conversations/{conversation_id}` | Restore persisted conversation history |
| `GET` | `/api/v1/debug/runs/{run_id}` | Inspect a persisted agent run |
| `GET` | `/api/v1/debug/conversations/{conversation_id}/runs` | Inspect runs for a conversation |

FastAPI also exposes interactive OpenAPI documentation at:

```text
/docs
```

---

# Agent Safety Limits

The multi-tool loop includes explicit safety boundaries:

```text
Maximum tool-call steps
Approved tool registry only
Pydantic argument validation
Unknown-tool rejection
Duplicate-call protection
Safe incomplete-result handling
Tool error handling
```

If the agent reaches its maximum investigation depth without enough evidence, it stops safely rather than continuing indefinitely.

---

# Guardrails

SupportPilot V2 is designed to:

- never invent customer information
- never invent subscription information
- never invent payment state
- never invent incidents
- never invent CloudDesk policies
- use approved tools for account-specific facts
- use the exact active customer ID
- ask for valid customer identification when required
- never expose another customer's data
- treat structured tool evidence as the source of truth
- distinguish semantic relevance from factual support
- investigate conflicting evidence rather than hide it
- never convert tool failure into a successful business conclusion
- avoid claiming unsupported state-changing actions were completed
- keep destructive account actions out of V2

Current prompt version:

```text
v2-multi-tool-2
```

---

# Testing

V2 was not considered complete until the full automated suite passed.

```text
55 passed
```

The suite covers:

- tool schemas
- payment tooling
- resolution logic
- orchestrator helpers
- health API
- support API
- conversation restoration
- customer UI
- Agent Inspector
- safe Markdown
- multi-tool workflows
- missing data
- invalid arguments
- tool failures
- maximum-step handling
- evidence conflict handling
- grounding protections
- resolution persistence
- trace persistence

Run:

```powershell
python -m pytest -q
```

Expected:

```text
55 passed
```

Automated workflow tests primarily use deterministic local systems and mocked Gemini behavior so normal test execution does not unnecessarily consume live model quota.

---

# Live Gemini Evaluation

V2 also went through a small live Gemini evaluation before completion.

Eight scenarios were manually validated:

```text
1. Flagship Pro-upgrade escalation
2. Conversational follow-up: "Why did it fail?"
3. Context-aware re-check: "Can you check that again?"
4. EU service incident diagnosis
5. Refund-policy knowledge grounding
6. Unsupported lifetime-plan grounding
7. Invalid customer handling
8. Pending payment handling
```

Final result:

```text
8 / 8 passed
```

The live evaluation exposed issues that were fixed before V2 was considered complete, including:

- embedding batching behavior
- contextual escalation wording
- distinguishing retrieved semantic candidates from sufficient factual evidence

---

# Local Setup

## 1. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

A Windows helper is also included:

```powershell
.\setup.ps1
```

---

## 3. Create PostgreSQL database

```sql
CREATE DATABASE clouddesk_support;
```

Connect:

```powershell
psql -U postgres -h localhost -d clouddesk_support
```

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Example:

```powershell
Copy-Item .env.example .env
```

Configure your local PostgreSQL connection and Gemini API key.

```env
APP_NAME=SupportPilot AI
APP_ENV=development

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/clouddesk_support

GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-2

EMBEDDING_DIMENSIONS=768
KNOWLEDGE_MIN_SCORE=0.55
MAX_AGENT_STEPS=5
```

> Never commit your real `.env` file.

---

## 5. Initialize CloudDesk data and knowledge embeddings

Normal setup:

```powershell
python -m scripts.bootstrap --embed
```

For a completely fresh synthetic SupportPilot database:

```powershell
python -m scripts.bootstrap --reset --embed
```

> `--reset` drops and recreates SupportPilot tables. Use it only when a clean synthetic database is intended.

---

## 6. Run tests

```powershell
python -m pytest -q
```

Expected:

```text
55 passed
```

---

## 7. Run SupportPilot

```powershell
python -m uvicorn app.main:app --reload
```

Customer UI:

```text
http://127.0.0.1:8000/
```

Agent Inspector:

```text
http://127.0.0.1:8000/debug
```

Swagger / OpenAPI:

```text
http://127.0.0.1:8000/docs
```

---

# Useful Manual Checks

Validate basic tool behavior:

```powershell
python -m scripts.manual_tool_check
```

Validate project structure:

```powershell
python -m scripts.check_structure
```

Regenerate missing knowledge embeddings:

```powershell
python -m scripts.embed_knowledge
```

---

# Security & Repository Hygiene

The repository excludes:

```text
.env
.venv/
__pycache__/
.pytest_cache/
.coverage
htmlcov/
.idea/
.vscode/
```

The repository must never contain:

- Gemini API keys
- PostgreSQL passwords
- production credentials
- real customer information

All CloudDesk data used by SupportPilot is synthetic.

---

# V2 Scope & Limitations

V2 is intentionally a local portfolio implementation, not a production customer-support platform.

The following are deliberately outside V2:

- real customer data
- real payment gateway integration
- production authentication
- real ticketing integrations
- automatic refunds
- automatic subscription changes
- automatic payment retries
- destructive/state-changing agent actions
- human approval workflows
- advanced long-term AI memory
- production cloud deployment

These capabilities are candidates for later versions.

---

# V1 → V2 Progression

## V1 — Agent Foundation

V1 established:

- Gemini tool calling
- business-system tools
- PostgreSQL persistence
- semantic retrieval
- grounding
- observability
- deterministic testing

V1 release:

```text
v1.0.0
28/28 automated tests
```

## V2 — Multi-Tool Resolution

V2 adds:

- fifth payment tool
- multi-tool investigations
- evidence accumulation
- cross-system conflict handling
- structured resolution outcomes
- conversation restoration
- contextual follow-ups
- stronger grounding behavior
- separate customer and internal interfaces
- Agent Inspector
- redesigned customer experience
- expanded automated testing
- live Gemini evaluation

V2 validation:

```text
55/55 automated tests
8/8 live Gemini scenarios
```

---

# V2 Completion Status

```text
Environment                          ✅
PostgreSQL                           ✅
Synthetic CloudDesk data             ✅
Five V2 tools                        ✅
Gemini tool calling                  ✅
Multi-tool orchestration             ✅
Payment domain                       ✅
Pydantic validation                  ✅
Semantic pgvector retrieval          ✅
Gemini embeddings                    ✅
Evidence grounding                   ✅
Conflict handling                    ✅
Resolution engine                    ✅
Conversation restoration             ✅
Conversational follow-ups            ✅
Persistence                          ✅
Agent Inspector                      ✅
Final customer UI                    ✅
Automated tests                      ✅ 55/55
Live Gemini evaluation               ✅ 8/8
Manual UI validation                 ✅
```

## SupportPilot AI — V2 Multi-Tool Resolution

**Status: COMPLETE ✅**

---

# Project Direction

SupportPilot is being developed version by version as an AI engineering / Forward Deployed Engineering portfolio project.

The goal is not only to demonstrate LLM integration, but to progressively explore:

- tool-using AI systems
- structured business-data integration
- retrieval and grounding
- agent observability
- failure handling
- customer-support workflows
- multi-step resolution
- human escalation
- controlled agent actions
- production-minded engineering practices

---

*Built locally as part of an AI / Forward Deployed Engineering portfolio.*
