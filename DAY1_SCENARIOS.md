# Day 1 Deterministic Support Scenarios

1. CUS-1001 asks: "What plan am I currently using?" -> get_subscription -> BASIC.
2. CUS-1002 asks: "Is my account active?" -> get_customer -> ACTIVE.
3. "Can I get a refund if I cancel my Pro subscription?" -> search_knowledge_base.
4. "Why can't I access CloudDesk right now?" -> get_service_status.
5. "Is there an outage in India?" -> get_service_status(service=core, region=IN) -> no active incident.
6. CUS-1002 asks to verify their upgraded plan -> get_subscription -> PRO.
7. Unknown CUS-9999 -> NOT_FOUND; no invented customer.
8. Valid customer without a subscription (add in a later seed case) -> NOT_FOUND; no invented plan.
9. Unsupported KB question -> NOT_FOUND; no fabricated policy.
10. CUS-1007 has BASIC shown, PRO requested, sync FAILED. Seed now; resolve in V2 after payment tool exists.
