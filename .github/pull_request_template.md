## Summary

<!-- What changed? Keep this concrete and scoped. -->

## Problem and User

<!-- What problem does this solve, and for which user or reviewer? -->

## Product Impact

<!-- Describe the user outcome, success measure, and any scope/non-goal changes. -->

## Technical Impact

<!-- Note affected runtime boundaries, APIs, schemas, dependencies, persistence, or operations. -->

## Governance Impact

<!-- Address agent autonomy, tool scope/provenance, policy behavior, approval, audit, privacy, and security. Write "None" with a reason when not applicable. -->

## Tests and Validation

- [ ] Automated tests added or updated
- [ ] `.venv/bin/pytest -q`
- [ ] Relevant failure and deny paths tested
- [ ] Documentation and demo behavior checked

**Commands and results**

```text
Paste exact commands and summarized results.
```

## Risks

<!-- Link risk-register IDs or describe likelihood, impact, mitigation, and residual risk. -->

## Decisions and Dependencies

<!-- Link decision-log entries, issues, migrations, rollout dependencies, or state "None." -->

## Screenshots or Demo Notes

<!-- Add API examples, audit evidence, or screenshots when behavior is visible. Do not include secrets or personal data. -->

## Rollback Plan

<!-- Explain how to return to the previous safe state. If rollback is not possible, say why and describe containment. -->

## Reviewer Checklist

- [ ] The change matches the issue acceptance criteria.
- [ ] No tool can execute before validation and policy evaluation.
- [ ] Approval remains bound to the evaluated action and tool version.
- [ ] New behavior emits sufficient audit evidence without unnecessary sensitive data.
- [ ] Failure, retry, and partial-state behavior is explicit.
- [ ] README, project status, backlog, risks, and decisions are updated where material.
