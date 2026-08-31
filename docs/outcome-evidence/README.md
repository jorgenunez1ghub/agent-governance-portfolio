# Outcome Evidence

This repository includes a pre-registered paired benchmark for reviewer/operator value.

The benchmark reuses the existing versioned policy evaluation scenarios rather than creating a second governance truth source. Its fixed eight-scenario subset covers allow, require-approval, deny, approval expiry, idempotent replay, terminal failure, retry, and path escalation.

## Structural validation

```bash
python -m evals.outcome_benchmark validate-config
```

## Initialize a run

Run the existing policy suite first, then initialize the evidence bundle before collecting assisted observations:

```bash
python -m evals.run_policy_evals
python -m evals.outcome_benchmark init \
  --run-id internal-paired-YYYYMMDD \
  --source-commit "$(git rev-parse HEAD)" \
  --participant-id reviewer-01 \
  --participant-role "independent internal governance reviewer"
```

Populate `baseline_results.csv` and `assisted_results.csv` for the same participant/scenario pairs. Baseline guardrail fields may remain blank because no governed runtime is executed in that phase. Assisted usefulness is required.

Before assisted data collection, save the exact versioned policy-evaluation result
inside the run bundle:

    python -m evals.outcome_benchmark record-policy-eval \
      --run-dir docs/outcome-evidence/<run_id>

The run metadata records the evaluated app version and commit, policy/eval
versions, scenario IDs, participant role labels, exceptions, and limitations.
Assisted guardrail counters must be explicit non-negative integers; blank cells
fail validation rather than being interpreted as zero.

Confirm that the frozen answer key, versions, policy result, participant labels,
and manifest digests agree before collection:

    python -m evals.outcome_benchmark validate-run \
      --run-dir docs/outcome-evidence/<run_id>

## Score and close out

```bash
python -m evals.outcome_benchmark summarize \
  --run-dir docs/outcome-evidence/<run_id>
```

The closeout is fail-closed:

- `STOP` for any execution guardrail violation, assisted disposition accuracy below 100%, or incomplete required evidence.
- `ADVANCE TO REPRESENTATIVE PILOT` only when all frozen productivity, usefulness, accuracy, evidence, and safety thresholds pass.
- `ITERATE` otherwise.

A solo/internal run must remain labeled **internal paired benchmark**. Do not call it production evidence or a representative pilot.
