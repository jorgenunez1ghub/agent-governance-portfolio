# Outcome Evidence Protocol v1

Status: **PRE-REGISTERED / NOT RUN**

This protocol implements Issue #1 as an internal paired benchmark. It measures whether the governed runtime improves reviewer decision and audit work while preserving fail-closed execution controls. It is not production evidence and must not be described as a representative pilot unless representative participants are recruited.

## Frozen question

For the same agent-proposed actions, does the governed runtime reduce the effort required to make a correct allow / require-approval / deny decision and reconstruct what happened while preventing unauthorized execution?

## Design

Use the eight fixed scenarios in `evals/scenarios/outcome_benchmark.v1.json`.

1. **Baseline:** the reviewer receives proposed action, tool, risk, and path context without governed-runtime decision outputs. Record disposition, rationale/audit notes, corrections, and elapsed decision and reconstruction time.
2. **Assisted:** the same reviewer uses governed runtime outputs, approval surface, receipts, path actions, and audit trail. Record the same fields plus usefulness.
3. Score both phases against the same generated `scenario_answer_key.json`.
4. Pair comparisons by `(participant_id, scenario_id)`.
5. Run the existing versioned policy evaluation suite on the evaluated commit before assisted data collection.

## Pre-registered metrics

- Correct governance disposition rate.
- Reviewer decision time in seconds.
- Audit reconstruction time in seconds.
- Reviewer correction burden.
- Approval friction, measured as review steps for approval-required scenarios.
- Reviewer usefulness on a 1–5 scale for assisted observations.

## Guardrails

For assisted observations:

- denied action executions = 0;
- approval-required actions executed before approval = 0;
- expired or rejected approval executions = 0;
- duplicate idempotency-key additional side effects = 0;
- required audit / receipt / path evidence completeness = 100%.

## Frozen success gate

`ADVANCE TO REPRESENTATIVE PILOT` requires all of the following:

- assisted governance disposition accuracy = 100% on all eight scenarios;
- median reviewer decision time improves by at least 30% versus baseline;
- median audit reconstruction time improves by at least 50%;
- all execution guardrails remain at zero violations;
- evidence completeness = 100%;
- median assisted usefulness >= 4/5.

`STOP` is mandatory if any execution guardrail is violated, assisted disposition accuracy is below 100%, or required evidence completeness is below 100%.

Otherwise the closeout is `ITERATE`.

## Run procedure

Initialize the bundle **before** assisted data collection:

```bash
python -m evals.outcome_benchmark init \
  --run-id internal-paired-YYYYMMDD \
  --source-commit "$(git rev-parse HEAD)"
```

Before collecting observations, record the policy evaluation and verify the frozen
bundle:

    python -m evals.outcome_benchmark record-policy-eval \
      --run-dir docs/outcome-evidence/<run_id>
    python -m evals.outcome_benchmark validate-run \
      --run-dir docs/outcome-evidence/<run_id>

After collecting paired observations:

```bash
python -m evals.outcome_benchmark summarize \
  --run-dir docs/outcome-evidence/<run_id>
```

The summary command validates scenario coverage, pairing, numeric fields, answer-key agreement, evidence completeness, and guardrails, then writes the closeout and file digests.

## Interpretation limits

A solo run is an **internal paired benchmark** only. Timing is sensitive to participant familiarity, environment, and ordering. Do not generalize to production or representative users without a separate participant protocol. Portfolio claims may be updated only from measured, validated evidence.
