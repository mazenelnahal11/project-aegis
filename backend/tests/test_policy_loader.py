from app.policy.loader import load_policy


def test_load_policy_from_yaml(tmp_path):
    p = tmp_path / "users.yaml"
    p.write_text(
        """
users:
  default:
    slack_id: U_ADMIN
  alice:
    slack_id: U_ALICE
  bob:
    slack_id: U_BOB
"""
    )
    pol = load_policy(p)
    assert pol.default_slack_id == "U_ADMIN"
    assert pol.slack_id_for("alice") == "U_ALICE"
    assert pol.slack_id_for("bob") == "U_BOB"
    assert pol.slack_id_for("nobody") == "U_ADMIN"  # falls back to default


def test_load_policy_missing_file_returns_empty(tmp_path):
    pol = load_policy(tmp_path / "does-not-exist.yaml")
    assert pol.default_slack_id == ""
    assert pol.slack_id_for("alice") == ""
