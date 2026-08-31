# SupportPilot AI — V2

SupportPilot AI is a local AI customer-support resolution agent for the fictional CloudDesk SaaS platform.

## Current V2 capabilities

- FastAPI chat API
- Gemini native tool/function calling
- PostgreSQL + pgvector
- Five read-only tools: customer, subscription, payment, service status, knowledge search
- Multi-tool investigations
- Structured resolution states: RESOLVED, NEEDS_INFORMATION, UNRESOLVED, ESCALATION_REQUIRED
- Cross-system conflict handling
- Tool-failure response guardrails
- Bounded recent conversational context
- Browser conversation restoration
- Safe Markdown rendering
- Customer UI at `/`
- Separate internal Agent Inspector at `/debug`
- Persisted run, tools, trace, resolution and final response

## Fresh setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and add your real PostgreSQL password and Gemini API key.

For a completely clean synthetic SupportPilot database:

```powershell
python -m scripts.bootstrap --reset --embed
```

To preserve existing rows and only bring the schema/data forward:

```powershell
python -m scripts.bootstrap --embed
```

Then:

```powershell
python -m pytest -q
uvicorn app.main:app --reload
```

Customer UI: `http://127.0.0.1:8000/`

Agent Inspector: `http://127.0.0.1:8000/debug`

Do not commit `.env`.

The current UI is intentionally the engineering-stage V2 UI. Final visual redesign is deferred until the engineering work is complete.
