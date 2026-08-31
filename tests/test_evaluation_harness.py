from evals.harness import DEFAULT_SUITE_PATH, load_suite, run_suite_sync


def test_versioned_policy_evaluation_suite_passes():
    suite = load_suite(DEFAULT_SUITE_PATH)

    assert suite.schema_version == "1.2.0"
    assert suite.policy_version == "agent-governance-policy-2.1"
    assert len(suite.scenarios) == 16

    result = run_suite_sync(suite)

    assert result.passed is True, {
        scenario.scenario_id: scenario.failures
        for scenario in result.scenarios
        if not scenario.passed
    }
    assert result.passed_count == result.total_count == 16
