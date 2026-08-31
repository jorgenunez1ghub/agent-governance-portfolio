import asyncio
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.agent.runtime import approve_approval, reject_approval, run_agent
from app.api.schemas import AgentRunRequest, AgentRunResponse, ApprovalActionResponse
from app.audit.logger import audit_logger
from app.config import settings
from app.governance.approvals import approval_store
from app.governance.approvers import approver_registry
from app.governance.path import execution_path_store
from app.tools.errors import RetryableToolExecutionError, TerminalToolExecutionError
from app.tools.registry import ToolProvenanceStatus, ToolRiskClass, tool_registry

DEFAULT_SUITE_PATH = Path(__file__).parent / "scenarios" / "policy_scenarios.v1.json"


class ToolOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    version: Optional[str] = None
    provenance_status: Optional[str] = None
    risk_class: Optional[str] = None


class ToolBehavior(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    mode: Literal["count_only", "fail_once_retryable", "fail_terminal"]


class ApprovalAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    approver_id: str = "demo-approver"


class ScenarioExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_status: str
    final_status: Optional[str] = None
    policy_outcome: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    tool_executed: bool
    required_events: List[str] = Field(default_factory=list)
    forbidden_events: List[str] = Field(default_factory=list)
    path_action_outcomes: List[str] = Field(default_factory=list)
    expected_exception: Optional[str] = None
    evaluated_path_action_count: Optional[int] = None
    approval_attempt_results: List[str] = Field(default_factory=list)
    execution_receipt_statuses: List[str] = Field(default_factory=list)
    approval_state: Optional[str] = None
    handler_call_count: Optional[int] = None
    idempotent_replay_count: Optional[int] = None
    authorization_denied_count: Optional[int] = None


class PolicyScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    mode: Literal["runtime", "approval_version_mismatch", "path_sequence"]
    request: Optional[AgentRunRequest] = None
    steps: List[AgentRunRequest] = Field(default_factory=list)
    approval_action: Optional[Literal["approve", "reject"]] = None
    approval_attempts: List[ApprovalAttempt] = Field(default_factory=list)
    approval_ttl_seconds: Optional[int] = None
    mismatch_version: Optional[str] = None
    tool_overrides: Optional[ToolOverrides] = None
    tool_behavior: Optional[ToolBehavior] = None
    expected: ScenarioExpectation


class PolicyEvaluationSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    suite_id: str
    policy_version: str
    scenarios: List[PolicyScenario]


class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    passed: bool
    failures: List[str] = Field(default_factory=list)
    event_count: int


class SuiteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str
    schema_version: str
    policy_version: str
    passed: bool
    passed_count: int
    total_count: int
    scenarios: List[ScenarioResult]


def load_suite(path: Path = DEFAULT_SUITE_PATH) -> PolicyEvaluationSuite:
    with path.open("r", encoding="utf-8") as file:
        return PolicyEvaluationSuite.model_validate(json.load(file))


async def run_suite(suite: PolicyEvaluationSuite) -> SuiteResult:
    original_audit_path = audit_logger.path
    results: List[ScenarioResult] = []

    try:
        for scenario in suite.scenarios:
            results.append(await _run_scenario(scenario))
    finally:
        approval_store.reset()
        execution_path_store.reset()
        audit_logger.configure_path(original_audit_path)

    passed_count = sum(result.passed for result in results)
    return SuiteResult(
        suite_id=suite.suite_id,
        schema_version=suite.schema_version,
        policy_version=suite.policy_version,
        passed=passed_count == len(results),
        passed_count=passed_count,
        total_count=len(results),
        scenarios=results,
    )


def run_suite_sync(suite: PolicyEvaluationSuite) -> SuiteResult:
    return asyncio.run(run_suite(suite))


async def _run_scenario(scenario: PolicyScenario) -> ScenarioResult:
    approval_store.reset()
    execution_path_store.reset()
    failures: List[str] = []
    exception_name: Optional[str] = None
    responses: List[AgentRunResponse] = []
    final_response: Optional[ApprovalActionResponse] = None
    approval_responses: List[ApprovalActionResponse] = []
    approval_attempt_results: List[str] = []
    handler_call_count = 0
    original_tools: Dict[str, Any] = {}
    version_mismatch_original = None
    original_approval_ttl = settings.approval_ttl_seconds

    with tempfile.TemporaryDirectory(prefix="agent-governance-eval-") as temp_dir:
        audit_logger.configure_path(Path(temp_dir) / "audit.jsonl")

        if scenario.approval_ttl_seconds is not None:
            settings.approval_ttl_seconds = scenario.approval_ttl_seconds

        if scenario.tool_overrides is not None:
            overrides = scenario.tool_overrides
            original_tool = tool_registry.get_tool(overrides.tool_name)
            original_tools.setdefault(overrides.tool_name, original_tool)
            replacement_fields: Dict[str, Any] = {}
            if overrides.version is not None:
                replacement_fields["version"] = overrides.version
            if overrides.provenance_status is not None:
                replacement_fields["provenance_status"] = ToolProvenanceStatus(overrides.provenance_status)
            if overrides.risk_class is not None:
                replacement_fields["risk_class"] = ToolRiskClass(overrides.risk_class)
            tool_registry._tools[overrides.tool_name] = replace(original_tool, **replacement_fields)

        if scenario.tool_behavior is not None:
            behavior = scenario.tool_behavior
            behavior_tool = tool_registry.get_tool(behavior.tool_name)
            original_tools.setdefault(behavior.tool_name, behavior_tool)
            original_handler = behavior_tool.handler

            async def controlled_handler(input_data):
                nonlocal handler_call_count
                handler_call_count += 1
                if behavior.mode == "fail_once_retryable" and handler_call_count == 1:
                    raise RetryableToolExecutionError(
                        code="eval_transient_failure",
                        message="Evaluation fixture transient failure.",
                    )
                if behavior.mode == "fail_terminal":
                    raise TerminalToolExecutionError(
                        code="eval_terminal_failure",
                        message="Evaluation fixture terminal failure.",
                    )
                return await original_handler(input_data)

            tool_registry._tools[behavior.tool_name] = replace(
                behavior_tool,
                handler=controlled_handler,
            )

        try:
            if scenario.mode == "path_sequence":
                responses = await _run_path_sequence(scenario)
            else:
                if scenario.request is None:
                    failures.append("Scenario request is required.")
                else:
                    response = await run_agent(scenario.request)
                    responses.append(response)

                    if scenario.mode == "approval_version_mismatch":
                        if response.approval_id is None or scenario.mismatch_version is None:
                            failures.append("Version-mismatch scenario requires an approval and mismatch_version.")
                        else:
                            tool_name = response.plan.tool_name if response.plan else ""
                            versioned_tool = tool_registry.get_tool(tool_name)
                            version_mismatch_original = versioned_tool
                            tool_registry._tools[tool_name] = replace(
                                versioned_tool,
                                version=scenario.mismatch_version,
                            )
                            try:
                                await approve_approval(
                                    response.approval_id,
                                    approver=approver_registry.get("demo-approver"),
                                )
                            except Exception as exc:
                                exception_name = type(exc).__name__
                    elif scenario.approval_attempts:
                        if response.approval_id is None:
                            failures.append("Approval attempts require an approval_id.")
                        else:
                            for attempt in scenario.approval_attempts:
                                try:
                                    attempt_response = await approve_approval(
                                        response.approval_id,
                                        approver=approver_registry.get(attempt.approver_id),
                                        idempotency_key=attempt.idempotency_key,
                                    )
                                    approval_responses.append(attempt_response)
                                    final_response = attempt_response
                                    approval_attempt_results.append(attempt_response.status)
                                except Exception as exc:
                                    approval_attempt_results.append(
                                        f"error:{type(exc).__name__}"
                                    )
                    elif scenario.approval_action is not None:
                        if response.approval_id is None:
                            failures.append("Approval action requested but response has no approval_id.")
                        elif scenario.approval_action == "approve":
                            final_response = await approve_approval(
                                response.approval_id,
                                approver=approver_registry.get("demo-approver"),
                            )
                        else:
                            final_response = await reject_approval(
                                response.approval_id,
                                approver=approver_registry.get("demo-approver"),
                            )
        finally:
            for tool_name, original_tool in original_tools.items():
                tool_registry._tools[tool_name] = original_tool
            if version_mismatch_original is not None:
                tool_registry._tools[version_mismatch_original.name] = version_mismatch_original
            settings.approval_ttl_seconds = original_approval_ttl

        events = await audit_logger.recent_events(limit=100)
        _assert_scenario(
            scenario=scenario,
            responses=responses,
            final_response=final_response,
            approval_responses=approval_responses,
            approval_attempt_results=approval_attempt_results,
            handler_call_count=handler_call_count,
            exception_name=exception_name,
            events=events,
            failures=failures,
        )

    return ScenarioResult(
        scenario_id=scenario.id,
        passed=not failures,
        failures=failures,
        event_count=len(events),
    )


async def _run_path_sequence(scenario: PolicyScenario) -> List[AgentRunResponse]:
    responses: List[AgentRunResponse] = []
    path_id: Optional[str] = None

    for step in scenario.steps:
        request = step.model_copy(update={"path_id": path_id}) if path_id else step
        response = await run_agent(request)
        responses.append(response)
        path_id = response.path_id

    return responses


def _assert_scenario(
    *,
    scenario: PolicyScenario,
    responses: List[AgentRunResponse],
    final_response: Optional[ApprovalActionResponse],
    approval_responses: List[ApprovalActionResponse],
    approval_attempt_results: List[str],
    handler_call_count: int,
    exception_name: Optional[str],
    events: List[Dict[str, Any]],
    failures: List[str],
) -> None:
    expected = scenario.expected
    if not responses:
        failures.append("Scenario produced no agent response.")
        return

    evaluated_response = responses[-1]
    _expect_equal(failures, "initial_status", evaluated_response.status, expected.initial_status)

    actual_final_status = final_response.status if final_response else None
    if expected.final_status is not None:
        _expect_equal(failures, "final_status", actual_final_status, expected.final_status)

    actual_policy_outcome = (
        evaluated_response.policy_decision.outcome.value
        if evaluated_response.policy_decision is not None
        else None
    )
    _expect_equal(failures, "policy_outcome", actual_policy_outcome, expected.policy_outcome)

    actual_reason_codes = (
        evaluated_response.policy_decision.reason_codes
        if evaluated_response.policy_decision is not None
        else []
    )
    _expect_equal(failures, "reason_codes", actual_reason_codes, expected.reason_codes)

    if expected.evaluated_path_action_count is not None:
        actual_path_count = (
            evaluated_response.policy_decision.evaluated_path_action_count
            if evaluated_response.policy_decision is not None
            else None
        )
        _expect_equal(
            failures,
            "evaluated_path_action_count",
            actual_path_count,
            expected.evaluated_path_action_count,
        )

    event_types = [event["event_type"] for event in events]
    for event_type in expected.required_events:
        if event_type not in event_types:
            failures.append(f"Missing required audit event: {event_type}")
    for event_type in expected.forbidden_events:
        if event_type in event_types:
            failures.append(f"Forbidden audit event observed: {event_type}")

    actual_tool_executed = "tool_executed" in event_types
    _expect_equal(failures, "tool_executed", actual_tool_executed, expected.tool_executed)
    _expect_equal(failures, "exception", exception_name, expected.expected_exception)
    _expect_equal(
        failures,
        "approval_attempt_results",
        approval_attempt_results,
        expected.approval_attempt_results,
    )

    if expected.handler_call_count is not None:
        _expect_equal(
            failures,
            "handler_call_count",
            handler_call_count,
            expected.handler_call_count,
        )
    if expected.idempotent_replay_count is not None:
        actual_replay_count = sum(response.idempotent_replay for response in approval_responses)
        _expect_equal(
            failures,
            "idempotent_replay_count",
            actual_replay_count,
            expected.idempotent_replay_count,
        )
    if expected.authorization_denied_count is not None:
        actual_denied_count = sum(
            event["event_type"] == "approval_authorization_denied"
            for event in events
        )
        _expect_equal(
            failures,
            "authorization_denied_count",
            actual_denied_count,
            expected.authorization_denied_count,
        )

    if evaluated_response.approval_id is not None:
        approval = approval_store.get(evaluated_response.approval_id)
        if expected.approval_state is not None:
            _expect_equal(
                failures,
                "approval_state",
                approval.status.value,
                expected.approval_state,
            )
        if "execution_receipt_statuses" in expected.model_fields_set:
            actual_receipt_statuses = [
                receipt.status.value
                for receipt in approval_store.list_receipts(evaluated_response.approval_id)
            ]
            _expect_equal(
                failures,
                "execution_receipt_statuses",
                actual_receipt_statuses,
                expected.execution_receipt_statuses,
            )

    path = execution_path_store.get(evaluated_response.path_id)
    actual_path_outcomes = [action.execution_outcome.value for action in path.actions]
    _expect_equal(
        failures,
        "path_action_outcomes",
        actual_path_outcomes,
        expected.path_action_outcomes,
    )

    failures.extend(_trace_completeness_failures(responses=responses, events=events))


def _trace_completeness_failures(
    *,
    responses: List[AgentRunResponse],
    events: List[Dict[str, Any]],
) -> List[str]:
    failures: List[str] = []
    terminal_types = {"approval_required", "run_completed", "run_denied", "run_failed"}

    for response in responses:
        run_events = [event for event in events if event.get("run_id") == response.run_id]
        event_types = {event["event_type"] for event in run_events}
        if "run_started" not in event_types:
            failures.append(f"{response.run_id}: missing run_started.")
        if not event_types.intersection(terminal_types):
            failures.append(f"{response.run_id}: missing terminal audit event.")
        if "path_action_recorded" not in event_types:
            failures.append(f"{response.run_id}: missing path_action_recorded.")
        else:
            record_index = next(
                index
                for index, event in enumerate(run_events)
                if event["event_type"] == "path_action_recorded"
            )
            terminal_indices = [
                index
                for index, event in enumerate(run_events)
                if event["event_type"] in terminal_types
            ]
            if terminal_indices and not any(index > record_index for index in terminal_indices):
                failures.append(
                    f"{response.run_id}: no terminal or pause event follows path_action_recorded."
                )

        for event in run_events:
            if event.get("path_id") != response.path_id:
                failures.append(f"{response.run_id}: event {event['event_type']} has the wrong path_id.")
            if event.get("path_action_id") != response.path_action_id:
                failures.append(
                    f"{response.run_id}: event {event['event_type']} has the wrong path_action_id."
                )

        policy_events = [event for event in run_events if event["event_type"] == "policy_evaluated"]
        for event in policy_events:
            for field in ("agent_id", "policy_decision_id", "tool_name", "tool_version"):
                if not event.get(field):
                    failures.append(f"{response.run_id}: policy_evaluated is missing {field}.")

        receipt_events = [
            event for event in run_events if event["event_type"] == "execution_receipt_recorded"
        ]
        for event in receipt_events:
            if not event.get("execution_receipt_id"):
                failures.append(
                    f"{response.run_id}: execution_receipt_recorded is missing execution_receipt_id."
                )
            if not event.get("approver_id"):
                failures.append(
                    f"{response.run_id}: execution_receipt_recorded is missing approver_id."
                )
            if not event.get("approval_authorization_decision_id"):
                failures.append(
                    f"{response.run_id}: execution_receipt_recorded is missing authorization decision."
                )

    return failures


def _expect_equal(failures: List[str], field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        failures.append(f"{field}: expected {expected!r}, got {actual!r}")
