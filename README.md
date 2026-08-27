# SupportPilot AI

AI Customer Support Resolution Agent for a fictional SaaS platform called **CloudDesk**.

**Project:** AI FDE Portfolio - Project 2  
**Current Version:** V1 - Agent Foundation  
**V1 Status:** Complete  
**Development Started:** 25 August 2026  
**Deployment:** Intentionally deferred until the portfolio projects are complete.

---

## Overview

SupportPilot AI is a tool-using AI customer-support agent built to investigate CloudDesk customer questions using structured business data and documented support knowledge.

Unlike a basic chatbot, SupportPilot does not rely only on the language model's internal knowledge.

For customer-specific or operational questions, the agent decides which approved tool it needs, executes that tool, receives structured evidence, and generates a response grounded in the returned data.

For documentation and policy questions, SupportPilot uses semantic retrieval powered by:

- Gemini embeddings
- PostgreSQL
- pgvector

The project also includes an optional Developer View that exposes the structured agent execution trace for debugging, testing, and portfolio demonstrations.

---

## V1 - Agent Foundation

V1 establishes the core agent architecture.

The V1 agent can:

- understand CloudDesk support requests;
- select an appropriate support tool;
- generate validated tool arguments;
- execute approved read-only tools;
- use structured tool responses as evidence;
- answer documented CloudDesk policy questions;
- perform semantic knowledge-base retrieval;
- avoid fabricating unsupported information;
- persist conversations, messages, agent runs, and tool executions;
- expose structured agent traces;
- handle invalid or unknown customer information safely;
- reject unrelated requests;
- provide a customer-facing web chat;
- optionally expose a Developer View for inspecting agent execution.

---

## Fictional SaaS Domain

SupportPilot operates against **CloudDesk**, a fictional SaaS platform created specifically for this project.

All customer records, subscriptions, incidents, and support documents are synthetic.

No real customer data is used.

---

# V1 Architecture

```text
Customer
   |
   v
SupportPilot Web UI
   |
   v
FastAPI
   |
   v
Agent Orchestrator
   |
   +-----------------------------+
   |                             |
   v                             v
Gemini Tool Selection      Gemini Final Response
   |
   v
Approved Support Tool
   |
   +-----------------------------+
   |              |              |
   v              v              v
PostgreSQL    pgvector      Knowledge Base
   |
   v
Structured Tool Result
   |
   v
Agent
   |
   v
Grounded Customer Response