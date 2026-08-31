from app.config import Settings


def test_approval_ttl_can_be_set_from_environment(monkeypatch):
    monkeypatch.setenv("APPROVAL_TTL_SECONDS", "120")

    assert Settings().approval_ttl_seconds == 120


def test_demo_approver_token_can_be_set_from_environment(monkeypatch):
    monkeypatch.setenv("DEMO_APPROVER_TOKEN", "environment-approver-token")

    assert Settings().demo_approver_token == "environment-approver-token"
