import csv
import json
import sys
from pathlib import Path

import pytest

from evals import outcome_benchmark as benchmark


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=benchmark.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_answer_key(path: Path, config: dict) -> None:
    (path / "scenario_answer_key.json").write_text(
        json.dumps(benchmark.answer_key(config), indent=2) + "\n",
        encoding="utf-8",
    )


def _write_valid_run_bundle(path: Path) -> None:
    config = benchmark.validate_config()
    frozen = benchmark.answer_key(config)
    source_commit = "a" * 40
    _write_answer_key(path, config)
    (path / "run_metadata.json").write_text(
        json.dumps(
            benchmark._run_metadata(
                run_id=path.name,
                source_commit=source_commit,
                config=config,
                participant_id="reviewer-1",
                participant_role="internal reviewer",
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "policy_eval_results.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "source_commit": source_commit,
                "result": {
                    **frozen["policy_suite"],
                    "passed": True,
                    "passed_count": 16,
                    "total_count": 16,
                    "scenarios": [],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for name in (
        "assisted_results.csv",
        "baseline_results.csv",
        "outcome_summary.md",
        "protocol.md",
        "reviewer_feedback.md",
    ):
        (path / name).write_text("placeholder\n", encoding="utf-8")
    benchmark.write_manifest(path, source_commit=source_commit, status="NOT_RUN")


def _row(
    scenario_id: str,
    decision: str,
    *,
    decision_seconds: float,
    audit_seconds: float,
    usefulness: str = "",
) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "participant_id": "reviewer-1",
        "decision": decision,
        "decision_seconds": decision_seconds,
        "audit_seconds": audit_seconds,
        "corrections": 0,
        "approval_steps": 2,
        "usefulness": usefulness,
        "audit_complete": "true",
        "denied_action_executions": 0,
        "preapproval_executions": 0,
        "expired_rejected_executions": 0,
        "duplicate_side_effects": 0,
        "notes": "",
    }


def _paired_rows(config: dict, decision_factor: float, audit_factor: float, assisted: bool):
    return [
        _row(
            item["scenario_id"],
            item["expected_disposition"],
            decision_seconds=100 * decision_factor,
            audit_seconds=120 * audit_factor,
            usefulness="5" if assisted else "",
        )
        for item in config["scenarios"]
    ]


def test_config_covers_required_governance_states():
    config = benchmark.validate_config()
    assert len(config["scenarios"]) == 8
    assert {item["coverage"] for item in config["scenarios"]} == set(config["required_coverage"])


def test_success_gate_advances(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    _write_rows(tmp_path / "baseline_results.csv", _paired_rows(config, 1.0, 1.0, False))
    _write_rows(tmp_path / "assisted_results.csv", _paired_rows(config, 0.6, 0.4, True))

    result = benchmark.summarize(tmp_path)

    assert result["closeout"] == "ADVANCE TO REPRESENTATIVE PILOT"
    assert result["assisted_accuracy"] == 1.0
    assert result["decision_time_improvement_pct"] == pytest.approx(40.0)
    assert result["audit_time_improvement_pct"] == pytest.approx(60.0)


def test_guardrail_violation_forces_stop(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    baseline = _paired_rows(config, 1.0, 1.0, False)
    assisted = _paired_rows(config, 0.6, 0.4, True)
    assisted[0]["denied_action_executions"] = 1
    _write_rows(tmp_path / "baseline_results.csv", baseline)
    _write_rows(tmp_path / "assisted_results.csv", assisted)

    assert benchmark.summarize(tmp_path)["closeout"] == "STOP"


def test_below_productivity_targets_iterates(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    _write_rows(tmp_path / "baseline_results.csv", _paired_rows(config, 1.0, 1.0, False))
    _write_rows(tmp_path / "assisted_results.csv", _paired_rows(config, 0.9, 0.8, True))

    assert benchmark.summarize(tmp_path)["closeout"] == "ITERATE"


def test_unpaired_rows_are_rejected(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    baseline = _paired_rows(config, 1.0, 1.0, False)
    assisted = _paired_rows(config, 0.6, 0.4, True)[:-1]
    _write_rows(tmp_path / "baseline_results.csv", baseline)
    _write_rows(tmp_path / "assisted_results.csv", assisted)

    with pytest.raises(benchmark.BenchmarkError, match="paired"):
        benchmark.summarize(tmp_path)


def test_blank_assisted_guardrail_is_rejected(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    baseline = _paired_rows(config, 1.0, 1.0, False)
    assisted = _paired_rows(config, 0.6, 0.4, True)
    assisted[0]["duplicate_side_effects"] = ""
    _write_rows(tmp_path / "baseline_results.csv", baseline)
    _write_rows(tmp_path / "assisted_results.csv", assisted)

    with pytest.raises(
        benchmark.BenchmarkError,
        match="assisted duplicate_side_effects is required",
    ):
        benchmark.summarize(tmp_path)


def test_modified_run_answer_key_is_rejected(tmp_path: Path):
    config = benchmark.validate_config()
    frozen = benchmark.answer_key(config)
    frozen["scenarios"][0]["expected_disposition"] = "deny"
    (tmp_path / "scenario_answer_key.json").write_text(
        json.dumps(frozen, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_rows(tmp_path / "baseline_results.csv", _paired_rows(config, 1.0, 1.0, False))
    _write_rows(tmp_path / "assisted_results.csv", _paired_rows(config, 0.6, 0.4, True))

    with pytest.raises(benchmark.BenchmarkError, match="answer key"):
        benchmark.summarize(tmp_path)


def test_summary_is_decision_ready(tmp_path: Path):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    _write_rows(tmp_path / "baseline_results.csv", _paired_rows(config, 1.0, 1.0, False))
    _write_rows(tmp_path / "assisted_results.csv", _paired_rows(config, 0.6, 0.4, True))

    summary = benchmark.render_summary(benchmark.summarize(tmp_path))

    assert "## Executive Summary" in summary
    assert "## Paired Results and Frozen Gates" in summary
    assert "## Safety and Audit Guardrails" in summary
    assert "## Recommended Next Step" in summary
    assert "not production evidence" in summary


def test_validate_run_rejects_missing_required_artifact(tmp_path: Path):
    _write_valid_run_bundle(tmp_path)
    (tmp_path / "reviewer_feedback.md").unlink()
    benchmark.write_manifest(tmp_path, source_commit="a" * 40, status="NOT_RUN")

    with pytest.raises(benchmark.BenchmarkError, match="required run files missing"):
        benchmark.validate_run(tmp_path)


def test_validate_run_rejects_manifest_tampering(tmp_path: Path):
    _write_valid_run_bundle(tmp_path)
    assert benchmark.validate_run(tmp_path)["inventory"] == "PASS"

    (tmp_path / "protocol.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(benchmark.BenchmarkError, match="manifest sha256 mismatch"):
        benchmark.validate_run(tmp_path)


def test_cli_reports_benchmark_error_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    config = benchmark.validate_config()
    _write_answer_key(tmp_path, config)
    _write_rows(tmp_path / "baseline_results.csv", [])
    _write_rows(tmp_path / "assisted_results.csv", [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "outcome_benchmark.py",
            "summarize",
            "--run-dir",
            str(tmp_path),
        ],
    )

    assert benchmark.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "baseline and assisted observations are both required" in captured.err
    assert "Traceback" not in captured.err
