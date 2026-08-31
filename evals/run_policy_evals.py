import argparse
import json
from pathlib import Path

from evals.harness import DEFAULT_SUITE_PATH, load_suite, run_suite_sync


def main() -> int:
    parser = argparse.ArgumentParser(description="Run versioned Agent Governance policy evaluations.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_SUITE_PATH,
        help="Path to a versioned policy scenario JSON file.",
    )
    parser.add_argument("--json", action="store_true", help="Print the complete result as JSON.")
    args = parser.parse_args()

    suite = load_suite(args.fixture)
    result = run_suite_sync(suite)

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    else:
        print(
            f"{result.suite_id} {result.policy_version}: "
            f"{result.passed_count}/{result.total_count} scenarios passed"
        )
        for scenario in result.scenarios:
            status = "PASS" if scenario.passed else "FAIL"
            print(f"{status} {scenario.scenario_id} ({scenario.event_count} audit events)")
            for failure in scenario.failures:
                print(f"  - {failure}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
