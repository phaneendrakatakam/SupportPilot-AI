# SupportPilot AI

> **AI customer-support resolution agent built with Gemini tool calling, FastAPI, PostgreSQL, pgvector, semantic retrieval, structured agent traces, and evidence-grounded responses.**

![Version](https://img.shields.io/badge/version-V1%20Agent%20Foundation-7C8CFF)
![Status](https://img.shields.io/badge/status-complete-brightgreen)
![Tests](https://img.shields.io/badge/tests-28%2F28%20passing-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791)
![Gemini](https://img.shields.io/badge/AI-Gemini-8E75FF)

**SupportPilot AI** is a local AI customer-support agent built around a fictional SaaS platform called **CloudDesk**.

Instead of allowing an LLM to answer customer questions from unrestricted model knowledge, SupportPilot can identify what information it needs, call approved support tools, retrieve structured business data or documented knowledge, and generate responses grounded in that evidence.

**Current release:** V1 — Agent Foundation  
**Status:** ✅ Complete  
**Automated tests:** 28/28 passing  
**Deployment:** Intentionally deferred

---

## Customer Experience

The default interface is designed as a clean customer-support chat experience. Internal agent execution details are hidden unless **Developer View** is enabled.

![SupportPilot Customer Mode](docs/V1/01_supportpilot_customer_mode.png)

---

## What V1 Demonstrates

SupportPilot V1 establishes the foundation for a tool-using support agent:

- Gemini-based intent understanding and tool selection
- Explicit native function/tool-calling loop
- Four approved read-only customer-support tools
- Pydantic validation for tool arguments
- PostgreSQL-backed customer and subscription data
- Service-incident lookup
- Semantic knowledge retrieval using Gemini embeddings + pgvector
- Evidence-grounded policy responses
- Hallucination guardrails
- Conversation, message, agent-run, and tool-execution persistence
- Structured Developer View / Agent Trace
- Tool latency and error tracking
- Prompt versioning
- Customer-facing browser interface
- 28 automated tests

---

# How SupportPilot Works

A customer request does not go directly from the LLM to an answer.

```text
Customer
   │
   ▼
SupportPilot Web UI
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
   ├── Decide whether a tool is required
   │
   ▼
Approved Support Tool
   │
   ├── PostgreSQL business data
   ├── Service incident data
   └── Semantic knowledge retrieval
   │
   ▼
Structured Tool Result
   │
   ▼
Gemini
   │
   ▼
Grounded Customer Response
```

Gemini's automatic function execution is intentionally disabled.

SupportPilot manages the function-calling loop explicitly so that tool selection, validated arguments, execution results, errors, latency, persistence, and traces remain visible to the application.

---

# V1 Support Tools

V1 exposes exactly four approved read-only tools.

| Tool | Purpose |
|---|---|
| `get_customer()` | Retrieve customer identity and account status |
| `get_subscription()` | Retrieve current plan, subscription status, requested plan and sync state |
| `get_service_status()` | Check active CloudDesk incidents/outages |
| `search_knowledge_base()` | Search documented CloudDesk support knowledge |

---

## Example — Subscription Investigation

Customer:

```text
What subscription plan am I currently on?
```

For the deterministic V1 test customer `CUS-1007`, SupportPilot calls:

```text
get_subscription(customer_id="CUS-1007")
```

The structured result contains:

```text
Current plan: BASIC
Subscription status: ACTIVE
Requested plan: PRO
Last sync status: FAILED
```

![Subscription Agent Trace](docs/V1/06_subscription_agent_trace.png)

The Developer View exposes:

- detected intent
- run ID
- selected tool
- tool arguments
- execution status
- latency
- structured result
- final customer response

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
Evidence-Grounded Answer
```

### Example

Customer:

```text
Can I get my money back after I cancel my subscription?
```

Even though the user does not explicitly ask for the **refund policy**, semantic retrieval identifies `refund_policy.md` as the strongest knowledge source.

![Semantic Knowledge Agent Trace](docs/V1/05_semantic_knowledge_agent_trace.png)

### Semantic stack

| Component | Implementation |
|---|---|
| Embedding model | `gemini-embedding-2` |
| Vector dimensions | 768 |
| Vector storage | PostgreSQL + pgvector |
| Retrieval | Cosine similarity |
| Agent knowledge tool | `search_knowledge_base()` |

---

# Grounding & Hallucination Control

One of the important V1 reliability lessons was that:

> **Semantic similarity is not the same as factual evidence.**

A vector search always tries to find the closest available passage. The closest passage, however, may still not actually answer the user's question.

For example:

```text
Does CloudDesk provide a lifetime subscription plan?
```

The knowledge base contains subscription-related material, but none of it establishes whether lifetime subscriptions exist.

SupportPilot therefore responds with uncertainty instead of inventing an answer.

![Grounding Guardrail](docs/V1/03_grounding_guardrail.png)

Correct behavior:

```text
The available CloudDesk documentation does not confirm
whether a lifetime subscription plan is offered.
```

Incorrect behavior would be:

```text
CloudDesk does not offer lifetime subscriptions.
```

The V1 grounding principle is:

```text
Missing evidence ≠ evidence that something is false
```

A high similarity score is treated as **candidate evidence**, not automatic proof.

---

# Service Status Investigation

SupportPilot can also inspect CloudDesk service-health information.

Example:

```text
Is the CloudDesk core service currently down in the EU region?
```

The agent selects:

```text
get_service_status()
```

and retrieves the seeded active EU incident.

![Service Status Agent Trace](docs/V1/04_service_status_agent_trace.png)

The deterministic V1 scenario includes:

```text
Incident: INC-2001
Service: Core
Region: EU
Severity: SEV2
Status: ACTIVE
```

---

# Customer Mode vs Developer View

SupportPilot separates the end-user experience from internal engineering visibility.

## Customer Mode

Customers see:

- support conversation
- customer ID field
- quick actions
- assistant responses
- message composer

They do **not** need to see internal tool calls or execution data.

![Subscription Response](docs/V1/02_subscription_response.png)

## Developer View

Developer View exposes structured agent execution information:

```text
Request
   ↓
Intent
   ↓
Tool Call
   ↓
Arguments
   ↓
Result Status
   ↓
Tool Result
   ↓
Latency
   ↓
Final Response
```

It is useful for:

- debugging
- QA
- support engineering
- agent evaluation
- portfolio demonstrations

---

# Technical Architecture

```text
app/
│
├── agent/
│   └── Agent orchestration, Gemini tool loop,
│       schemas and guardrails
│
├── api/
│   └── FastAPI routes
│
├── db/
│   └── PostgreSQL models, connection and seed data
│
├── services/
│   └── Supporting AI services such as embeddings
│
├── tools/
│   └── Agent capabilities
│
├── templates/
│   └── Customer interface HTML
│
└── static/
    └── CSS + JavaScript
```

Additional project areas:

```text
knowledge_base/
└── Synthetic CloudDesk support documents

scripts/
└── Setup utilities and manual agent/tool checks

tests/
├── unit/
├── integration/
├── workflows/
└── evaluation/

docs/
└── V1/
    └── Portfolio screenshots
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
service_incidents
documents
document_chunks
conversations
messages
agent_runs
tool_executions
```

A typical tool-using interaction leaves a persistent trail:

```text
Conversation
     │
     ▼
User Message
     │
     ▼
Agent Run
     │
     ▼
Tool Execution
     │
     ▼
Assistant Message
```

Tool executions record information such as:

- tool name
- arguments
- execution status
- result
- latency
- error details

Failed agent runs can also be persisted for debugging.

---

# Synthetic CloudDesk Environment

CloudDesk is a fictional SaaS platform created specifically for SupportPilot.

No real customer data is used.

Important deterministic V1 scenarios include:

| ID | Scenario |
|---|---|
| `CUS-1001` | Active customer |
| `CUS-1003` | Suspended customer |
| `CUS-1007` | Basic plan, Pro upgrade requested, latest sync failed |
| `INC-2001` | Active SEV2 CloudDesk core incident in EU |

These scenarios make development and testing repeatable.

---

# Knowledge Base

The V1 knowledge base contains synthetic CloudDesk documentation such as:

```text
refund_policy.md
subscription_changes.md
service_status.md
support_scope.md
```

These documents are used only for the fictional CloudDesk environment.

---

# API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Customer SupportPilot UI |
| `GET` | `/health` | Application/database/agent health |
| `POST` | `/api/v1/support/chat` | Process a customer support request |

FastAPI also exposes interactive OpenAPI documentation at:

```text
/docs
```

---

# Guardrails

SupportPilot V1 is instructed to:

- never invent customer information
- never invent subscription information
- never invent incidents
- never invent CloudDesk policies
- use approved tools for account-specific facts
- use the exact active customer ID
- ask for a customer ID when required
- never expose another customer's data
- treat tool results as the source of truth
- distinguish semantic relevance from factual support
- avoid claiming unsupported actions were completed
- handle unknown records safely
- keep unrelated questions outside CloudDesk support scope

Current prompt version:

```text
v1-agent-foundation-3
```

---

# Testing

V1 was not considered complete until the full automated suite passed.

```text
28 passed
```

The suite includes:

- Pydantic schema validation
- FastAPI health tests
- support API tests
- UI tests
- tool-contract tests
- deterministic database scenarios
- agent workflow tests
- mocked Gemini orchestration tests
- persistence tests
- trace validation
- invalid-tool argument handling
- evidence-grounding checks
- pgvector readiness checks
- embedding-dimension checks
- final V1 acceptance tests

Mocked Gemini workflow tests avoid consuming live API quota.

Live Gemini routing and semantic retrieval behavior were also manually validated during development.

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
python -m pip install -r requirements.txt
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

Exit:

```text
\q
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

Configure your local database connection and Gemini API key.

Example:

```env
APP_NAME=CloudDesk Support Agent
APP_ENV=development
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/clouddesk_support
GEMINI_API_KEY=your_api_key_here
```

> Never commit your real `.env` file.

---

## 5. Seed CloudDesk data

```powershell
python -m app.db.seed
```

---

## 6. Prepare semantic knowledge embeddings

```powershell
python -m scripts.prepare_semantic_kb
```

This generates and stores 768-dimensional Gemini embeddings in PostgreSQL/pgvector.

---

## 7. Run SupportPilot

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## 8. Run tests

```powershell
python -m pytest -q
```

Expected V1 result:

```text
28 passed
```

---

# Useful Manual Checks

Check the four support tools:

```powershell
python -m scripts.manual_tool_check
```

Check Gemini agent behavior:

```powershell
python -m scripts.manual_agent_check
```

Check tool routing:

```powershell
python -m scripts.manual_agent_routing_check
```

Check guardrails:

```powershell
python -m scripts.manual_agent_guardrail_check
```

---

# Security & Repository Hygiene

The repository excludes:

```text
.env
.venv/
__pycache__/
.pytest_cache/
.idea/
.vscode/
```

The repository must never contain:

- Gemini API keys
- PostgreSQL passwords
- production credentials
- real customer information

All CloudDesk data used in V1 is synthetic.

---

# V1 Scope & Limitations

V1 is intentionally an **Agent Foundation**, not a complete production support platform.

The following are deliberately outside V1:

- complex multi-tool investigations
- payment-status tooling
- state-changing support actions
- approval workflows
- formal resolution states
- escalation workflows
- production authentication/authorization
- production deployment
- production monitoring
- full conversational memory replay

### Browser refresh behavior

Messages and agent activity are persisted in PostgreSQL for traceability.

However, the current V1 frontend does not reload an existing conversation after a browser refresh. Browser-session restoration and full conversational memory are planned for a later version.

---

# V2 — Multi-Tool Resolution

V2 will move SupportPilot from primarily single-tool support questions toward multi-step issue investigation.

Example:

```text
Customer:
"I paid for Pro, but my account still shows Basic."
                │
                ▼
          get_customer()
                │
                ▼
       get_subscription()
                │
                ▼
       get_payment_status()
                │
                ▼
         Compare Evidence
                │
                ▼
      Determine Resolution
          ┌─────┴─────┐
          ▼           ▼
      RESOLVED    ESCALATION_REQUIRED
```

Planned V2 focus:

- multi-tool investigation
- payment-status tooling
- structured resolution states
- richer execution traces
- explicit escalation decisions
- stronger failure handling

---

# V1 Completion Status

```text
Environment                     ✅
PostgreSQL                       ✅
Synthetic CloudDesk data         ✅
Four V1 tools                    ✅
Gemini tool calling              ✅
Manual agent loop                ✅
Pydantic validation              ✅
Semantic pgvector retrieval      ✅
Gemini embeddings                ✅
Evidence grounding               ✅
Guardrails                       ✅
Persistence                      ✅
Agent trace                      ✅
Customer Mode                    ✅
Developer View                   ✅
Automated tests                  ✅ 28/28
```

## SupportPilot AI — V1 Agent Foundation

**Status: COMPLETE ✅**

---

## Project Direction

SupportPilot is being developed version by version as an AI engineering / Forward Deployed Engineering portfolio project.

The goal is not only to demonstrate LLM integration, but to progressively explore:

- tool-using AI systems
- structured business-data integration
- retrieval and grounding
- agent observability
- failure handling
- customer-support workflows
- multi-step resolution
- production-minded engineering practices

---

*Built locally as part of an AI / Forward Deployed Engineering portfolio.*
