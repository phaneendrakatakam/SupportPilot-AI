# SupportPilot AI

### Human-in-the-Loop AI Support Investigation & Resolution System

SupportPilot AI is a portfolio-grade AI support system that investigates customer issues, gathers evidence through read-only tools, recommends controlled actions, requires human approval before any state-changing operation, executes approved actions through the backend, verifies the resulting state, and then produces a grounded customer-safe response.

The project evolved across three major versions:

**V1 — Understand + Retrieve**  
**V2 — Investigate + Resolve**  
**V3 — Investigate + Recommend + Approve + Act + Verify**

V3 is the final major version of SupportPilot AI.

---

## Why I Built This

Many AI support demos stop after generating an answer.

SupportPilot AI explores a harder problem:

> **How can an AI system investigate a real support issue, recommend an operational action, involve a human at the correct decision point, safely execute that action, verify what actually happened, and communicate the result without overclaiming?**

The project was designed to demonstrate practical AI engineering concepts including:

- Agentic investigation
- Multi-tool orchestration
- Retrieval-grounded support
- Human-in-the-loop workflows
- Controlled backend actions
- Approval and execution separation
- Idempotency
- Customer isolation
- Transaction rollback
- Post-action verification
- Auditability
- Failure-aware customer communication
- Automated evaluation and security validation

---

# V3 Architecture

SupportPilot AI V3 follows this lifecycle:

```text
Customer Problem
      ↓
AI Investigation
      ↓
Read-Only Tool Calls
      ↓
Evidence Collection
      ↓
Structured Resolution
      ↓
Action Recommendation
      ↓
Human Approval / Rejection
      ↓
Explicit Execution
      ↓
Backend Safety Validation
      ↓
Controlled Action
      ↓
Post-Action Verification
      ↓
Grounded Customer Response
      ↓
Audit Trail
```

### Core Principle

The LLM is allowed to:

- investigate
- reason over tool results
- collect evidence
- classify the issue
- recommend an action

The LLM is **not allowed to directly perform business mutations**.

All state-changing operations remain under deterministic backend control.

---

## System Architecture

```mermaid
flowchart TD
    A[Customer Request] --> B[AI Investigation]

    B --> C[Read-Only Tool Registry]

    C --> D[Customer]
    C --> E[Subscription]
    C --> F[Payment]
    C --> G[Service Status]
    C --> H[Knowledge Base]

    D --> I[Evidence + Structured Resolution]
    E --> I
    F --> I
    G --> I
    H --> I

    I --> J{Action Required?}

    J -->|No| K[Grounded Customer Response]

    J -->|Yes| L[Action Proposal]

    L --> M[Human Review]

    M -->|Reject| N[No Business Mutation]
    M -->|Approve| O[Explicit Execute]

    O --> P[Backend Validation]
    P --> Q[Controlled Action]
    Q --> R[Post-Action Verification]

    R -->|Verified| S[Customer-Safe Final Response]
    R -->|Failed| T[Escalation / Safe Failure State]

    N --> U[Audit Trail]
    S --> U
    T --> U
```

---

# Read-Only AI Tool Boundary

Gemini receives access only to investigation tools:

```text
get_customer()
get_subscription()
get_payment_status()
get_service_status()
search_knowledge_base()
```

These tools allow the model to understand the issue without changing customer or business state.

The V3 action layer is intentionally **not registered as an LLM tool**.

This separation creates a clear security boundary:

```text
AI → investigate and recommend
Backend → validate and execute
Human → authorize
```

---

# Controlled Actions

V3 introduces three controlled business actions.

| Action | Purpose | State Change | Verification |
|---|---|---|---|
| `retry_subscription_sync()` | Repair a verified paid upgrade where subscription synchronization failed | Updates simulated subscription state | Subscription is independently re-read and must match the requested plan |
| `create_support_ticket()` | Escalate an unresolved or unsafe-to-remediate issue | Creates a support case | Ticket is re-read and validated |
| `request_refund_review()` | Create a human billing review for an explicit refund request | Creates a refund-review record | Review record must exist in `PENDING_REVIEW` |

---

## Important Refund Safety Boundary

SupportPilot AI **never automatically issues refunds**.

A successful refund workflow creates a review request such as:

```text
RR-XXXXXXXXXXXX
Status: PENDING_REVIEW
```

The original payment remains unchanged.

This allows the system to acknowledge and track the request without falsely claiming that money was returned.

---

# Human-in-the-Loop Workflow

Approval and execution are intentionally separate operations.

```text
PENDING_APPROVAL
       ↓
Human Approves
       ↓
APPROVED
       ↓
Still No Mutation
       ↓
Explicit Execute
       ↓
EXECUTING
       ↓
SUCCEEDED / FAILED
       ↓
Post-Action Verification
       ↓
VERIFIED / FAILED
```

An approval alone does **not** modify customer state.

Execution must be triggered separately.

---

# V3 Safety & Integrity Controls

The action layer implements several safeguards designed around real operational failure modes.

### Server-Side Approval Enforcement

A pending or rejected proposal cannot execute.

Approval state is checked by the backend rather than trusted from the frontend.

### Exact Action Allow-List

Only these actions may execute:

```text
retry_subscription_sync
create_support_ticket
request_refund_review
```

Unknown or tampered action names are rejected.

### Customer Isolation

Before execution, the backend revalidates relationships between:

- proposal
- conversation
- agent run
- customer
- payment
- action arguments

Cross-customer mutations are blocked.

### Precondition Revalidation

Conditions are checked again immediately before execution.

The system does not assume that the state observed during investigation is still valid.

### Idempotency

Repeated execution requests cannot perform the same business mutation multiple times.

### Transaction Safety

State-changing business operations execute inside a database savepoint.

If an action fails after partially mutating state:

```text
Business mutation → ROLLBACK
Audit execution record → PRESERVED
```

### Verified-Write Rule

A state-changing action is committed only when post-action verification succeeds.

Execution success alone is not treated as proof of resolution.

### Rejection Safety

Rejected proposals cause zero business-state changes.

Where appropriate, the system can generate a safer escalation proposal instead.

---

# User Interfaces

SupportPilot separates three different audiences.

## Customer Workspace

Route:

```text
/
```

Designed for end customers.

The customer interface contains:

- conversational support
- customer-safe status
- resolution messages
- case references
- refund-review references

It deliberately hides:

- proposal IDs
- action names
- approval controls
- execution controls
- internal payloads
- raw traces
- technical audit data

### Customer Workspace

![SupportPilot AI Customer Workspace](docs/V3/v3_01_customer_ui_home_final.png)

---

## Operations Workspace

Route:

```text
/operations
```

Designed for the human operator reviewing AI recommendations.

It provides:

- review queue
- customer context
- investigation evidence
- turn outcome
- overall case state
- recommended action
- approval/rejection controls
- separate execution control
- execution status
- verification status
- before/after state
- escalation handoff
- collapsed technical audit details

### Pending Human Approval

![Pending Subscription Approval](docs/V3/v3_02_operations_pending_approval_subscription_final.png)

### Approved Action — Awaiting Explicit Execution

![Approved Awaiting Execution](docs/V3/v3_03_operations_approved_awaiting_execution_final.png)

### Verified Subscription Remediation

![Verified Subscription Resolution](docs/V3/v3_04_operations_subscription_verified_final.png)

---

## Engineering Inspector

Route:

```text
/debug
```

The debug surface is intended for structured application observability.

It exposes technical execution information without exposing private model chain-of-thought.

---

# Flagship V3 Workflows

## 1. Subscription Upgrade Remediation

Example customer state:

```text
Customer: CUS-1007
Current Plan: BASIC
Requested Plan: PRO
Payment: SUCCESS
Subscription Sync: FAILED
```

Investigation finds sufficient evidence that the customer successfully paid for the requested upgrade but account synchronization failed.

The AI recommends:

```text
retry_subscription_sync
```

The human approves the proposal.

No state changes yet.

The human explicitly executes the approved action.

The backend:

1. revalidates customer and subscription state
2. verifies successful payment for the requested plan
3. retries the simulated synchronization
4. independently re-reads subscription state
5. confirms:

```text
Plan: PRO
Sync: SUCCESS
```

Only then is the case considered resolved.

### Customer Resolution

![Customer Subscription Resolved](docs/V3/v3_05_customer_subscription_resolved_final.png)

---

## 2. Refund Review

A customer explicitly requests a refund after a verified successful payment.

The AI investigates the payment and relevant support policy.

Rather than directly refunding the transaction, it recommends:

```text
request_refund_review
```

After human approval and explicit execution, the backend creates a review record:

```text
RR-XXXXXXXXXXXX
Status: PENDING_REVIEW
```

The payment remains:

```text
SUCCESS
```

### Verified Refund Review

![Refund Review Verified](docs/V3/v3_06_operations_refund_review_verified_final.png)

The customer receives a safe response explaining that the refund request has been submitted for human review and that no refund was automatically issued.

---

## 3. Support Ticket Escalation

Example:

```text
Customer: CUS-1005
Current Plan: BASIC
Requested Plan: PRO
Subscription Sync: FAILED
Payment Evidence: NOT FOUND
```

Retrying the subscription synchronization would be unsafe because successful payment cannot be verified.

The system therefore recommends:

```text
create_support_ticket
```

Following approval and execution, a support ticket is created with:

- customer context
- issue type
- priority
- evidence
- summary
- case status

### Verified Support Ticket

![Support Ticket Verified](docs/V3/v3_07_operations_support_ticket_verified_final.png)

### Customer Escalation State

![Customer Case Escalated](docs/V3/v3_08_customer_case_escalated_final.png)

The customer receives a case reference without being falsely told that the underlying problem has already been resolved.

---

# Customer Case States

SupportPilot distinguishes between an AI turn outcome and the overall customer case.

Examples include:

```text
RESOLVED
CASE_OPEN
UNDER_REVIEW
NEEDS_SUPPORT
APPROVED_AWAITING_EXECUTION
```

This prevents a successful tool call or action proposal from being confused with actual issue resolution.

---

# API Highlights

### Actions

```text
GET  /api/v1/actions
GET  /api/v1/actions/{proposal_id}

POST /api/v1/actions/{proposal_id}/approve
POST /api/v1/actions/{proposal_id}/reject
POST /api/v1/actions/{proposal_id}/execute
```

### Customer Case

```text
GET /api/v1/support/conversations/{conversation_id}/case-status
```

The frontend never bypasses these backend controls.

---

# Validation & Testing

V3 was validated through automated regression testing, deterministic evaluation, security auditing, and manual end-to-end workflow testing.

| Validation | Result |
|---|---:|
| Automated pytest suite | **144 / 144 PASS** |
| Formal deterministic V3 evaluation | **14 / 14 PASS** |
| Security / repository audit | **18 / 18 PASS** |
| Final flagship manual E2E workflows | **3 / 3 PASS** |
| Final UI visual review | **PASS** |

---

## Formal Evaluation Scenarios

The deterministic evaluation covers scenarios including:

- successful paid upgrade with failed synchronization
- missing payment evidence
- explicit refund request
- pending payment
- failed payment
- already-refunded payment
- cross-customer conflicts
- cross-plan conflicts
- service incidents
- invalid customers
- tool failures
- knowledge-base misses
- weak semantic evidence
- already-completed upgrades

Run the evaluation with:

```powershell
python -m scripts.run_v3_evaluation
```

---

# Security Audit

The repository includes a repeatable V3 security audit covering:

- `.env` exclusion
- secret scanning
- safe `.env.example`
- read-only Gemini tool registry
- exact controlled-action allow-list
- server-side approval enforcement
- unknown-action rejection
- duplicate execution protection
- customer isolation
- verified-write rollback
- lifecycle persistence
- customer UI action isolation
- private reasoning exposure checks
- synthetic-data verification
- repository-noise checks

Run:

```powershell
python -m scripts.run_v3_security_audit
```

Validated result:

```text
18 PASS
0 WARN
0 FAIL

Security/repository audit: PASS
```

---

# Technology Stack

### Backend

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy-style relational persistence
- Pydantic validation

### AI

- Google Gemini
- Tool calling
- Structured responses
- Retrieval-grounded support investigation

### Knowledge Layer

- Local Markdown knowledge base
- Semantic retrieval
- Evidence-grounded resolution

### Frontend

- HTML
- CSS
- Vanilla JavaScript

### Quality

- pytest
- deterministic scenario evaluation
- integration testing
- workflow testing
- security/repository audit

---

# Project Structure

```text
SupportPilot-AI/
│
├── app/
│   ├── actions/
│   │   ├── recommendations.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── tools.py
│   │
│   ├── agent/
│   ├── api/
│   ├── db/
│   ├── services/
│   ├── static/
│   ├── templates/
│   └── tools/
│
├── docs/
│   ├── V1/
│   ├── V2/
│   └── V3/
│
├── knowledge_base/
│
├── scripts/
│   ├── bootstrap.py
│   ├── embed_knowledge.py
│   ├── run_v3_evaluation.py
│   └── run_v3_security_audit.py
│
├── tests/
│   ├── evaluation/
│   ├── integration/
│   ├── unit/
│   └── workflows/
│
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

---

# Running SupportPilot AI Locally

## 1. Clone the Repository

```powershell
git clone <repository-url>
cd SupportPilot-AI
```

## 2. Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

## 4. Configure Environment Variables

Create `.env` from the provided template:

```powershell
Copy-Item .env.example .env
```

Configure the local values, including your Gemini API key and PostgreSQL connection.

Example:

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

Never commit the real `.env` file.

## 5. Prepare the Local Environment

Ensure PostgreSQL is running and the configured database is available.

Then run:

```powershell
python -m scripts.bootstrap
python -m scripts.embed_knowledge
```

## 6. Start the Application

```powershell
uvicorn app.main:app --reload
```

Open:

```text
Customer UI
http://127.0.0.1:8000/

Operations
http://127.0.0.1:8000/operations

Engineering Inspector
http://127.0.0.1:8000/debug
```

---

# Running the Test Suite

```powershell
pytest
```

Current V3 baseline:

```text
144 passed
```

---

# Version Evolution

| Version | Focus | Key Evolution |
|---|---|---|
| **V1** | Understand + Retrieve | AI support foundation, read-only tools, grounded investigation |
| **V2** | Investigate + Resolve | Multi-tool investigation, stronger resolution logic, richer support workflow |
| **V3** | Recommend + Approve + Act + Verify | Human-in-the-loop actions, execution controls, verification, rollback, isolation and auditability |

### Architectural Evolution

```text
V1
Understand + Retrieve

        ↓

V2
Investigate + Resolve

        ↓

V3
Investigate + Recommend + Approve + Act + Verify
```

V3 represents the final major architectural milestone for SupportPilot AI.

Future changes, if required, will be maintenance-level improvements rather than a new major version.

---

# What V3 Demonstrates

SupportPilot AI is not intended to demonstrate only prompt engineering.

The project demonstrates how an AI model can be placed inside a controlled software system where probabilistic reasoning and deterministic business logic have clearly separated responsibilities.

### AI Responsibilities

```text
Understand
Investigate
Retrieve
Correlate
Recommend
Explain
```

### Application Responsibilities

```text
Authorize
Validate
Mutate
Persist
Rollback
Verify
Audit
```

### Human Responsibilities

```text
Review
Approve
Reject
Trigger execution
Own high-impact decisions
```

That separation is the central architectural idea behind SupportPilot AI V3.

---

# Portfolio Scope

SupportPilot AI is a **synthetic portfolio project**.

The included customers, subscriptions, payments, tickets, refund reviews and support scenarios are simulated for demonstration and testing.

The project does not connect to real:

- payment processors
- refund systems
- customer accounts
- CRM platforms
- production support systems

Controlled actions modify only the project's local simulated business state.

Production concerns such as enterprise authentication, authorization/RBAC, external system integration, deployment infrastructure, rate limiting and production observability would require additional implementation before real-world use.

---

# Project Status

```text
SupportPilot AI V3
FINAL MAJOR VERSION

Automated Tests            144 / 144 PASS
Formal Evaluation           14 / 14 PASS
Security Audit              18 / 18 PASS
Manual E2E                   3 / 3 PASS
UI Review                         PASS
```

**SupportPilot AI V3 is feature-complete as a portfolio project.**

Deployment is intentionally treated as a separate future exercise rather than part of the V3 application milestone.

---

## Author

**Phaneendra Katakam**

Cloud & DevOps Engineer transitioning toward AI / Forward Deployed Engineering, with a focus on building practical AI systems that combine investigation, operational workflows, human decision points, backend safety and measurable outcomes.

---

> **SupportPilot AI V3 — Investigate. Recommend. Approve. Act. Verify.**
