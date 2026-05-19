from unittest.mock import patch

from app.notifiers.base import NullNotifier


def test_null_notifier_records_calls():
    n = NullNotifier()
    n.send_grace_warning(
        owner_id="U1", owner_label="alice",
        action_summary="kill PID 1", reason="hot", deadline_iso="2026-01-01T00:00:00Z",
        ack_url="http://x/y",
    )
    assert len(n.sent) == 1
    assert n.sent[0]["owner_label"] == "alice"


def test_slack_notifier_requires_webhook(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    from app.notifiers.slack import SlackNotifier
    import pytest
    with pytest.raises(RuntimeError):
        SlackNotifier()


def test_slack_notifier_posts_block_kit(monkeypatch):
    from app.notifiers.slack import SlackNotifier
    n = SlackNotifier(webhook_url="https://hooks.example/aaa")

    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): return None
    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    with patch("app.notifiers.slack.httpx.post", side_effect=fake_post):
        n.send_grace_warning(
            owner_id="U123", owner_label="alice",
            action_summary="PID 4821 will be terminated", reason="long runtime",
            deadline_iso="2026-05-19T12:00:00Z", ack_url="http://localhost/api/grace/ack/abc",
        )

    assert captured["url"] == "https://hooks.example/aaa"
    body = captured["json"]
    assert "<@U123>" in body["text"]
    assert any("Acknowledge" in str(b).lower() or "ack" in str(b).lower() for b in body["blocks"])


def test_factory_picks_null_when_no_webhook(monkeypatch):
    from app.config import settings
    from app.notifiers import factory
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    factory.reset_notifier_cache()
    n = factory.get_notifier()
    assert n.name == "null"
    factory.reset_notifier_cache()


def test_factory_picks_slack_when_webhook_set(monkeypatch):
    from app.config import settings
    from app.notifiers import factory
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.example/zzz")
    factory.reset_notifier_cache()
    n = factory.get_notifier()
    assert n.name == "slack"
    factory.reset_notifier_cache()
