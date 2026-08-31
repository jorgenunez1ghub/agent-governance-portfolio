# Milestone 1.5

## Goal

Build an async FastAPI backend that demonstrates the core runtime pattern for a governed agent system:

```text
user request -> async context retrieval + mock model planning -> tool registry lookup -> Pydantic validation -> policy check -> human approval gate when required -> tool execution -> audit logging
```

## In Scope

- Async FastAPI service.
- Mock context retrieval.
- Mock model planning.
- `asyncio.gather()` for concurrent retrieval and planning.
- Tool registry with three tools.
- Pydantic tool input validation.
- Policy approval check.
- In-memory approval store.
- JSONL audit log.
- Focused tests.

## Out of Scope

- Real model provider calls.
- Vector database retrieval.
- Authentication.
- User interface.
- Production deployment.
- Persistent approval database.
- Agent identity registry.
- Path-aware policy evaluation.
- Tool provenance scanning.
- Rollback management.
- Runtime monitoring dashboard.

## Definition of Done

- A safe task executes immediately.
- A risky external task returns `approval_required`.
- Approving the risky task executes the tool.
- Invalid tool input fails before execution.
- `app/storage/audit_log.jsonl` contains structured events for the run.
- `pytest` passes.

## Strategic Fit

This milestone is the smallest executable proof of governed agent execution. It demonstrates the "act with approval" pattern for a risky external tool while leaving deeper governance concerns to later milestones.

See [research-context.md](research-context.md) for notes on proportional autonomy governance, path-aware policy, agent identity, and tool supply-chain risk.
