from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from evals.harness import load_suite, run_suite_sync

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "evals" / "scenarios" / "outcome_benchmark.v1.json"
POLICY_PATH = ROOT / "evals" / "scenarios" / "policy_scenarios.v1.json"
PROTOCOL_PATH = ROOT / "docs" / "outcome-evidence" / "protocol.v1.md"
PYPROJECT_PATH = ROOT / "pyproject.toml"

CSV_FIELDS = [
    "scenario_id",
    "participant_id",
    "decision",
    "decision_seconds",
    "audit_seconds",
    "corrections",
    "approval_steps",
    "usefulness",
    "audit_complete",
    "denied_action_executions",
    "preapproval_executions",
    "expired_rejected_executions",
    "duplicate_side_effects",
    "notes",
]
REQUIRED_RUN_FILES = {
    "assisted_results.csv",
    "baseline_results.csv",
    "outcome_summary.md",
    "policy_eval_results.json",
    "protocol.md",
    "reviewer_feedback.md",
    "run_metadata.json",
    "scenario_answer_key.json",
}


class BenchmarkError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    return _load_json(CONFIG_PATH)


def validate_config() -> dict[str, Any]:
    config = load_config()
    policy = _load_json(POLICY_PATH)
    scenarios = config["scenarios"]
    required = set(config["required_coverage"])

    ids = [item["scenario_id"] for item in scenarios]
    coverages = [item["coverage"] for item in scenarios]
    if len(scenarios) < 8:
        raise BenchmarkError("benchmark requires at least eight scenarios")
    if len(ids) != len(set(ids)):
        raise BenchmarkError("scenario IDs must be unique")
    if set(coverages) != required:
        raise BenchmarkError("benchmark coverage does not match required coverage")

    policy_by_id = {item["id"]: item for item in policy["scenarios"]}
    missing = sorted(set(ids) - set(policy_by_id))
    if missing:
        raise BenchmarkError(f"benchmark scenarios missing from policy suite: {missing}")

    for item in scenarios:
        actual = policy_by_id[item["scenario_id"]].get("expected", {}).get("policy_outcome")
        if actual != item["expected_disposition"]:
            raise BenchmarkError(
                f"{item['scenario_id']} disposition mismatch: {actual!r} != "
                f"{item['expected_disposition']!r}"
            )
    return config


def answer_key(config: dict[str, Any]) -> dict[str, Any]:
    policy = _load_json(POLICY_PATH)
    return {
        "schema_version": config["schema_version"],
        "benchmark_id": config["benchmark_id"],
        "source_policy_suite": config["source_policy_suite"],
        "policy_suite": {
            "schema_version": policy["schema_version"],
            "suite_id": policy["suite_id"],
            "policy_version": policy["policy_version"],
        },
        "targets": config["targets"],
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "coverage": item["coverage"],
                "expected_disposition": item["expected_disposition"],
                "expected_terminal_outcome": item["expected_terminal_outcome"],
            }
            for item in config["scenarios"]
        ],
    }


def _app_version() -> str:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def _run_metadata(
    *,
    run_id: str,
    source_commit: str,
    config: dict[str, Any],
    participant_id: str | None = None,
    participant_role: str | None = None,
) -> dict[str, Any]:
    key = answer_key(config)
    participant_roles = (
        {participant_id: participant_role}
        if participant_id is not None and participant_role is not None
        else {}
    )
    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "evidence_class": "internal paired benchmark",
        "source_commit": source_commit,
        "app_version": _app_version(),
        "benchmark": {
            "benchmark_id": key["benchmark_id"],
            "schema_version": key["schema_version"],
            "scenario_ids": [item["scenario_id"] for item in key["scenarios"]],
        },
        "policy_suite": key["policy_suite"],
        "participant_roles": participant_roles,
        "exceptions": [],
        "limitations": [],
    }


def _write_csv_header(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=CSV_FIELDS).writeheader()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(run_dir: Path, *, source_commit: str, status: str) -> None:
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            inventory[path.name] = {
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
    manifest = {
        "schema_version": "1.0.0",
        "benchmark_id": load_config()["benchmark_id"],
        "run_id": run_dir.name,
        "source_commit": source_commit,
        "status": status,
        "evidence_class": "internal paired benchmark",
        "inventory": inventory,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def validate_manifest_inventory(run_dir: Path) -> None:
    manifest = _load_json(run_dir / "manifest.json")
    inventory = manifest.get("inventory", {})
    actual_names = {
        path.name
        for path in run_dir.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    if set(inventory) != actual_names:
        raise BenchmarkError("manifest inventory does not match run files")
    for name, expected in inventory.items():
        path = run_dir / name
        if expected.get("sha256") != _sha256(path):
            raise BenchmarkError(f"manifest sha256 mismatch: {name}")
        if expected.get("bytes") != path.stat().st_size:
            raise BenchmarkError(f"manifest byte count mismatch: {name}")


def init_run(
    run_id: str,
    source_commit: str,
    *,
    participant_id: str | None = None,
    participant_role: str | None = None,
) -> Path:
    config = validate_config()
    if (participant_id is None) != (participant_role is None):
        raise BenchmarkError(
            "participant_id and participant_role must be provided together"
        )
    run_dir = ROOT / "docs" / "outcome-evidence" / run_id
    if run_dir.exists():
        raise BenchmarkError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    (run_dir / "protocol.md").write_text(
        PROTOCOL_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "scenario_answer_key.json").write_text(
        json.dumps(answer_key(config), indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            _run_metadata(
                run_id=run_id,
                source_commit=source_commit,
                config=config,
                participant_id=participant_id,
                participant_role=participant_role,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv_header(run_dir / "baseline_results.csv")
    _write_csv_header(run_dir / "assisted_results.csv")
    (run_dir / "reviewer_feedback.md").write_text(
        "# Reviewer Feedback\n\n"
        "Run status: NOT RUN\n\n"
        "Record participant role labels, qualitative usefulness feedback, exceptions, "
        "and limitations here. Do not include secrets or sensitive personal data.\n",
        encoding="utf-8",
    )
    (run_dir / "outcome_summary.md").write_text(
        "# Outcome Summary\n\nStatus: **NOT RUN**\n\n"
        "No outcome claim is valid until paired observations are collected and "
        "`python -m evals.outcome_benchmark summarize` succeeds.\n",
        encoding="utf-8",
    )
    write_manifest(run_dir, source_commit=source_commit, status="NOT_RUN")
    return run_dir


def _rows(path: Path, phase: str) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise BenchmarkError(f"{path.name} header does not match benchmark schema")
        rows = list(reader)

    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        if not row["scenario_id"] or not row["participant_id"] or not row["decision"]:
            raise BenchmarkError(f"{path.name}:{index} missing required identity/decision field")
        try:
            decision_seconds = float(row["decision_seconds"])
            audit_seconds = float(row["audit_seconds"])
            corrections = int(row["corrections"])
            approval_steps = int(row["approval_steps"] or 0)
        except ValueError as exc:
            raise BenchmarkError(f"{path.name}:{index} has invalid numeric field") from exc
        if decision_seconds < 0 or audit_seconds < 0 or corrections < 0 or approval_steps < 0:
            raise BenchmarkError(f"{path.name}:{index} contains negative metrics")

        usefulness = None
        if row["usefulness"]:
            try:
                usefulness = float(row["usefulness"])
            except ValueError as exc:
                raise BenchmarkError(f"{path.name}:{index} usefulness must be numeric") from exc
            if not 1 <= usefulness <= 5:
                raise BenchmarkError(f"{path.name}:{index} usefulness must be 1..5")
        if phase == "assisted" and usefulness is None:
            raise BenchmarkError(f"{path.name}:{index} assisted usefulness is required")

        audit_complete = row["audit_complete"].strip().lower()
        if audit_complete not in {"true", "false"}:
            raise BenchmarkError(f"{path.name}:{index} audit_complete must be true/false")

        guardrails: dict[str, int | None] = {}
        for field in (
            "denied_action_executions",
            "preapproval_executions",
            "expired_rejected_executions",
            "duplicate_side_effects",
        ):
            raw = row[field].strip()
            if phase == "baseline" and raw == "":
                guardrails[field] = None
                continue
            if phase == "assisted" and raw == "":
                raise BenchmarkError(
                    f"{path.name}:{index} assisted {field} is required"
                )
            try:
                value = int(raw)
            except ValueError as exc:
                raise BenchmarkError(f"{path.name}:{index} {field} must be integer") from exc
            if value < 0:
                raise BenchmarkError(f"{path.name}:{index} {field} cannot be negative")
            guardrails[field] = value

        parsed.append(
            {
                **row,
                "phase": phase,
                "decision_seconds": decision_seconds,
                "audit_seconds": audit_seconds,
                "corrections": corrections,
                "approval_steps": approval_steps,
                "usefulness": usefulness,
                "audit_complete": audit_complete == "true",
                **guardrails,
            }
        )
    return parsed


def _pct_improvement(baseline: float, assisted: float) -> float:
    if baseline <= 0:
        raise BenchmarkError("baseline median time must be greater than zero")
    return ((baseline - assisted) / baseline) * 100.0


def _load_frozen_answer_key(run_dir: Path) -> dict[str, Any]:
    frozen = _load_json(run_dir / "scenario_answer_key.json")
    expected = answer_key(validate_config())
    if frozen != expected:
        raise BenchmarkError(
            "run answer key does not match the versioned benchmark configuration"
        )
    return frozen


def summarize(run_dir: Path) -> dict[str, Any]:
    frozen = _load_frozen_answer_key(run_dir)
    key = {item["scenario_id"]: item for item in frozen["scenarios"]}
    expected_ids = set(key)

    baseline = _rows(run_dir / "baseline_results.csv", "baseline")
    assisted = _rows(run_dir / "assisted_results.csv", "assisted")
    if not baseline or not assisted:
        raise BenchmarkError("baseline and assisted observations are both required")

    def pairs(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
        result = [(row["participant_id"], row["scenario_id"]) for row in rows]
        if len(result) != len(set(result)):
            raise BenchmarkError("duplicate participant/scenario observation")
        return set(result)

    baseline_pairs = pairs(baseline)
    assisted_pairs = pairs(assisted)
    if baseline_pairs != assisted_pairs:
        raise BenchmarkError("baseline and assisted observations must be paired")
    observed_ids = {scenario_id for _, scenario_id in baseline_pairs}
    if observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise BenchmarkError(f"scenario coverage mismatch; missing={missing}, extra={extra}")

    for rows in (baseline, assisted):
        for row in rows:
            if row["scenario_id"] not in key:
                raise BenchmarkError(f"unknown scenario: {row['scenario_id']}")
            row["decision_correct"] = (
                row["decision"] == key[row["scenario_id"]]["expected_disposition"]
            )

    baseline_accuracy = sum(r["decision_correct"] for r in baseline) / len(baseline)
    assisted_accuracy = sum(r["decision_correct"] for r in assisted) / len(assisted)
    baseline_decision = median(r["decision_seconds"] for r in baseline)
    assisted_decision = median(r["decision_seconds"] for r in assisted)
    baseline_audit = median(r["audit_seconds"] for r in baseline)
    assisted_audit = median(r["audit_seconds"] for r in assisted)
    decision_improvement = _pct_improvement(baseline_decision, assisted_decision)
    audit_improvement = _pct_improvement(baseline_audit, assisted_audit)
    usefulness = median(r["usefulness"] for r in assisted if r["usefulness"] is not None)
    evidence_completeness = sum(r["audit_complete"] for r in assisted) / len(assisted)
    corrections_baseline = sum(r["corrections"] for r in baseline)
    corrections_assisted = sum(r["corrections"] for r in assisted)
    approval_steps = [
        r["approval_steps"]
        for r in assisted
        if key[r["scenario_id"]]["expected_disposition"] == "require_approval"
    ]
    median_approval_steps = median(approval_steps) if approval_steps else 0.0

    guardrail_fields = (
        "denied_action_executions",
        "preapproval_executions",
        "expired_rejected_executions",
        "duplicate_side_effects",
    )
    guardrail_totals = {
        field: sum(int(r[field] or 0) for r in assisted) for field in guardrail_fields
    }
    guardrail_violations = sum(guardrail_totals.values())

    targets = frozen["targets"]
    if (
        guardrail_violations > 0
        or assisted_accuracy < targets["assisted_disposition_accuracy"]
        or evidence_completeness < targets["evidence_completeness"]
    ):
        closeout = "STOP"
    elif (
        decision_improvement >= targets["decision_time_improvement_pct"]
        and audit_improvement >= targets["audit_time_improvement_pct"]
        and usefulness >= targets["median_usefulness"]
    ):
        closeout = "ADVANCE TO REPRESENTATIVE PILOT"
    else:
        closeout = "ITERATE"

    return {
        "closeout": closeout,
        "paired_observations": len(baseline),
        "participants": len({r["participant_id"] for r in baseline}),
        "baseline_accuracy": baseline_accuracy,
        "assisted_accuracy": assisted_accuracy,
        "baseline_median_decision_seconds": baseline_decision,
        "assisted_median_decision_seconds": assisted_decision,
        "decision_time_improvement_pct": decision_improvement,
        "baseline_median_audit_seconds": baseline_audit,
        "assisted_median_audit_seconds": assisted_audit,
        "audit_time_improvement_pct": audit_improvement,
        "baseline_corrections": corrections_baseline,
        "assisted_corrections": corrections_assisted,
        "median_approval_steps": median_approval_steps,
        "median_usefulness": usefulness,
        "evidence_completeness": evidence_completeness,
        "guardrails": guardrail_totals,
        "targets": targets,
    }


def _validate_run_context(
    run_dir: Path,
    *,
    participants: set[str],
    frozen: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = _load_json(run_dir / "run_metadata.json")
    manifest = _load_json(run_dir / "manifest.json")
    evaluation = _load_json(run_dir / "policy_eval_results.json")

    if metadata.get("run_id") != run_dir.name:
        raise BenchmarkError("run metadata run_id does not match directory")
    if metadata.get("evidence_class") != "internal paired benchmark":
        raise BenchmarkError("run metadata evidence_class is invalid")
    if metadata.get("source_commit") != manifest.get("source_commit"):
        raise BenchmarkError("run metadata source_commit does not match manifest")
    if metadata.get("app_version") != _app_version():
        raise BenchmarkError("run metadata app_version does not match project")
    if metadata.get("policy_suite") != frozen.get("policy_suite"):
        raise BenchmarkError("run metadata policy suite does not match answer key")
    benchmark = metadata.get("benchmark", {})
    if benchmark.get("benchmark_id") != frozen.get("benchmark_id"):
        raise BenchmarkError("run metadata benchmark ID does not match answer key")
    if benchmark.get("schema_version") != frozen.get("schema_version"):
        raise BenchmarkError("run metadata benchmark schema does not match answer key")
    if benchmark.get("scenario_ids") != [
        item["scenario_id"] for item in frozen["scenarios"]
    ]:
        raise BenchmarkError("run metadata scenario IDs do not match answer key")

    roles = metadata.get("participant_roles", {})
    missing_roles = sorted(participants - set(roles))
    if missing_roles or any(not str(roles[item]).strip() for item in participants):
        raise BenchmarkError(f"participant role labels missing for: {missing_roles}")
    if not isinstance(metadata.get("exceptions"), list):
        raise BenchmarkError("run metadata exceptions must be a list")
    if not isinstance(metadata.get("limitations"), list):
        raise BenchmarkError("run metadata limitations must be a list")

    result = evaluation.get("result", {})
    if evaluation.get("source_commit") != manifest.get("source_commit"):
        raise BenchmarkError("policy evaluation source_commit does not match manifest")
    if any(
        result.get(field) != frozen["policy_suite"][field]
        for field in ("schema_version", "suite_id", "policy_version")
    ):
        raise BenchmarkError("policy evaluation version does not match answer key")
    if not result.get("passed") or result.get("passed_count") != result.get("total_count"):
        raise BenchmarkError("policy evaluation must pass before closeout")
    return metadata, evaluation


def validate_run(run_dir: Path) -> dict[str, Any]:
    frozen = _load_frozen_answer_key(run_dir)
    metadata = _load_json(run_dir / "run_metadata.json")
    participants = set(metadata.get("participant_roles", {}))
    if not participants:
        raise BenchmarkError("at least one participant role label is required")
    actual_names = {
        path.name
        for path in run_dir.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    missing_files = sorted(REQUIRED_RUN_FILES - actual_names)
    if missing_files:
        raise BenchmarkError(f"required run files missing: {missing_files}")
    _validate_run_context(
        run_dir,
        participants=participants,
        frozen=frozen,
    )
    validate_manifest_inventory(run_dir)
    return {
        "run_id": run_dir.name,
        "status": _load_json(run_dir / "manifest.json").get("status"),
        "participants": len(participants),
        "scenarios": len(frozen["scenarios"]),
        "policy_evaluation": "PASS",
        "inventory": "PASS",
    }


def record_policy_evaluation(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "manifest.json")
    suite = load_suite(POLICY_PATH)
    result = run_suite_sync(suite)
    payload = {
        "schema_version": "1.0.0",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": manifest.get("source_commit", "UNKNOWN"),
        "result": result.model_dump(mode="json"),
    }
    (run_dir / "policy_eval_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    write_manifest(
        run_dir,
        source_commit=manifest.get("source_commit", "UNKNOWN"),
        status=manifest.get("status", "NOT_RUN"),
    )
    return payload


def render_summary(
    result: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> str:
    guardrails = "\n".join(
        f"- {name.replace('_', ' ')}: {value}" for name, value in result["guardrails"].items()
    )
    decision_gate = result["targets"]["decision_time_improvement_pct"]
    audit_gate = result["targets"]["audit_time_improvement_pct"]
    usefulness_gate = result["targets"]["median_usefulness"]
    source = ""
    caveats = [
        "This is a single-participant internal paired benchmark, not production "
        "evidence or a representative-user pilot.",
        "Timing is sensitive to participant familiarity, scenario ordering, and "
        "the local measurement environment.",
    ]
    if metadata is not None:
        policy = metadata["policy_suite"]
        source = (
            f"- Evaluated app: version {metadata['app_version']} at source commit "
            f"{metadata['source_commit']}\n"
            f"- Policy/eval contract: {policy['policy_version']} / schema "
            f"{policy['schema_version']}\n"
        )
        caveats.extend(str(item) for item in metadata.get("limitations", []))
    caveat_lines = "\n".join(f"- {item}" for item in dict.fromkeys(caveats))
    next_step = (
        "Run the frozen protocol with representative reviewers before making broader "
        "portfolio or production claims."
        if result["closeout"] == "ADVANCE TO REPRESENTATIVE PILOT"
        else "Address the failed gates, then repeat the internal paired benchmark "
        "before recruiting representative reviewers."
    )
    return (
        "# Governed-Agent Review and Audit Value\n\n"
        "## Executive Summary\n\n"
        f"- **Closeout: {result['closeout']}.** The governed-runtime review "
        f"workflow was scored across {result['paired_observations']} paired scenarios "
        f"from {result['participants']} internal participant.\n"
        f"- **Decision time changed by {result['decision_time_improvement_pct']:.1f}%.** "
        f"The frozen advance gate is at least {decision_gate:.1f}% improvement.\n"
        f"- **Audit reconstruction time changed by "
        f"{result['audit_time_improvement_pct']:.1f}%.** The frozen advance gate is "
        f"at least {audit_gate:.1f}% improvement.\n"
        f"- **Safety evidence remained explicit.** Assisted disposition accuracy was "
        f"{result['assisted_accuracy']:.1%}, evidence completeness was "
        f"{result['evidence_completeness']:.1%}, and recorded guardrail violations "
        f"totaled {sum(result['guardrails'].values())}.\n\n"
        "## Paired Results and Frozen Gates\n\n"
        "| Measure | Baseline | Assisted | Change / status | Frozen gate |\n"
        "|---|---:|---:|---:|---:|\n"
        f"| Disposition accuracy | {result['baseline_accuracy']:.1%} | "
        f"{result['assisted_accuracy']:.1%} | "
        f"{result['assisted_accuracy'] - result['baseline_accuracy']:+.1%} | "
        f"{result['targets']['assisted_disposition_accuracy']:.1%} assisted |\n"
        f"| Median decision time | {result['baseline_median_decision_seconds']:.2f}s | "
        f"{result['assisted_median_decision_seconds']:.2f}s | "
        f"{result['decision_time_improvement_pct']:.1f}% improvement | "
        f">= {decision_gate:.1f}% |\n"
        f"| Median audit reconstruction | {result['baseline_median_audit_seconds']:.2f}s | "
        f"{result['assisted_median_audit_seconds']:.2f}s | "
        f"{result['audit_time_improvement_pct']:.1f}% improvement | "
        f">= {audit_gate:.1f}% |\n"
        f"| Material corrections | {result['baseline_corrections']} | "
        f"{result['assisted_corrections']} | "
        f"{result['assisted_corrections'] - result['baseline_corrections']:+d} | "
        "descriptive |\n"
        f"| Median usefulness | n/a | {result['median_usefulness']:.1f}/5 | "
        f"assisted only | >= {usefulness_gate:.1f}/5 |\n"
        f"| Evidence completeness | n/a | {result['evidence_completeness']:.1%} | "
        f"assisted only | {result['targets']['evidence_completeness']:.1%} |\n\n"
        "Approval-required scenarios took a median "
        f"{result['median_approval_steps']:.1f} review steps in the assisted phase. "
        "This is a descriptive friction measure, not a production latency claim.\n\n"
        "## Safety and Audit Guardrails\n\n"
        f"{guardrails}\n\n"
        "All four counters must remain at zero for an advance decision. Required "
        "audit, receipt, and path evidence must remain complete for every assisted "
        "scenario.\n\n"
        "## Recommended Next Step\n\n"
        f"{next_step}\n\n"
        "## Further Questions\n\n"
        "- Do representative reviewers reproduce the time improvements without prior "
        "answer-key familiarity?\n"
        "- Which approval steps create the most friction, and can any be removed "
        "without weakening authorization evidence?\n\n"
        "## Caveats and Assumptions\n\n"
        f"{caveat_lines}\n\n"
        "## Source Context\n\n"
        "Evidence class: **internal paired benchmark**\n\n"
        f"{source}"
        f"- Paired observations: {result['paired_observations']}\n"
        f"- Participants: {result['participants']}\n"
    )


def summarize_and_write(run_dir: Path) -> dict[str, Any]:
    result = summarize(run_dir)
    frozen = _load_frozen_answer_key(run_dir)
    baseline = _rows(run_dir / "baseline_results.csv", "baseline")
    metadata, _ = _validate_run_context(
        run_dir,
        participants={row["participant_id"] for row in baseline},
        frozen=frozen,
    )
    (run_dir / "outcome_summary.md").write_text(
        render_summary(result, metadata=metadata), encoding="utf-8"
    )
    manifest = _load_json(run_dir / "manifest.json")
    write_manifest(
        run_dir,
        source_commit=manifest.get("source_commit", "UNKNOWN"),
        status=result["closeout"],
    )
    validate_manifest_inventory(run_dir)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Outcome evidence paired benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-config")

    init = sub.add_parser("init")
    init.add_argument("--run-id", required=True)
    init.add_argument("--source-commit", required=True)
    init.add_argument("--participant-id")
    init.add_argument("--participant-role")

    summary = sub.add_parser("summarize")
    summary.add_argument("--run-dir", type=Path, required=True)

    record_eval = sub.add_parser("record-policy-eval")
    record_eval.add_argument("--run-dir", type=Path, required=True)

    validate = sub.add_parser("validate-run")
    validate.add_argument("--run-dir", type=Path, required=True)
    return parser


def _execute(args: argparse.Namespace) -> int:
    if args.command == "validate-config":
        config = validate_config()
        print(f"OUTCOME_BENCHMARK_CONFIG_OK scenarios={len(config['scenarios'])}")
        return 0
    if args.command == "init":
        print(
            init_run(
                args.run_id,
                args.source_commit,
                participant_id=args.participant_id,
                participant_role=args.participant_role,
            )
        )
        return 0
    if args.command == "summarize":
        print(json.dumps(summarize_and_write(args.run_dir), indent=2))
        return 0
    if args.command == "record-policy-eval":
        payload = record_policy_evaluation(args.run_dir)
        print(json.dumps(payload["result"], indent=2))
        return 0 if payload["result"]["passed"] else 1
    if args.command == "validate-run":
        print(json.dumps(validate_run(args.run_dir), indent=2))
        return 0
    raise AssertionError(args.command)


def main() -> int:
    args = _parser().parse_args()
    try:
        return _execute(args)
    except BenchmarkError as exc:
        print(f"OUTCOME_BENCHMARK_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
