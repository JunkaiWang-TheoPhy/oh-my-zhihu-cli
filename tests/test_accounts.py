"""Multi-account behavior for Web Session and Official API backends."""

from __future__ import annotations

import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from zhihu_cli.accounts import AccountStore, InvalidAccountName
from zhihu_cli.auth import cookie_str_to_dict, get_cookie_string
from zhihu_cli.cli import cli


class MemorySecrets:
    def __init__(self):
        self.values: dict[str, str] = {}

    def set(self, name: str, secret: str) -> None:
        self.values[name] = secret

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def test_session_accounts_keep_independent_cookies_and_switch_active_account(tmp_path):
    store = AccountStore(tmp_path, secret_store=MemorySecrets())
    store.save_session("personal", {"z_c0": "one", "_xsrf": "x1", "d_c0": "d1"})
    store.save_session("work", {"z_c0": "two", "_xsrf": "x2", "d_c0": "d2"})

    assert store.active_name("session") == "work"
    assert store.active_session_cookies()["z_c0"] == "two"

    store.use("personal", "session")

    assert store.active_session_cookies()["z_c0"] == "one"
    assert [item.name for item in store.list("session")] == ["personal", "work"]


def test_legacy_cookie_file_migrates_to_default_without_losing_login(tmp_path):
    legacy = tmp_path / "cookies.json"
    legacy.write_text(
        json.dumps({"cookies": {"z_c0": "old", "_xsrf": "x", "d_c0": "d"}}),
        encoding="utf-8",
    )

    store = AccountStore(tmp_path, secret_store=MemorySecrets())

    assert store.active_name("session") == "default"
    assert store.active_session_cookies()["z_c0"] == "old"
    assert store.list("session")[0].name == "default"


def test_api_accounts_store_only_metadata_on_disk_and_secret_in_keychain(tmp_path):
    secrets = MemorySecrets()
    store = AccountStore(tmp_path, secret_store=secrets)

    store.save_api("personal", "secret-one")
    store.save_api("work", "secret-two")
    store.use("personal", "api")

    assert store.active_api_secret() == "secret-one"
    assert "secret-one" not in (tmp_path / "accounts.json").read_text(encoding="utf-8")
    assert [item.name for item in store.list("api")] == ["personal", "work"]


def test_removing_active_account_selects_remaining_account(tmp_path):
    store = AccountStore(tmp_path, secret_store=MemorySecrets())
    store.save_session("one", {"z_c0": "1"})
    store.save_session("two", {"z_c0": "2"})

    store.remove("two", "session")

    assert store.active_name("session") == "one"
    assert store.active_session_cookies()["z_c0"] == "1"


@pytest.mark.parametrize("name", ["", "../escape", "a/b", "a" * 65])
def test_account_names_reject_empty_paths_and_overlong_values(tmp_path, name):
    store = AccountStore(tmp_path, secret_store=MemorySecrets())

    with pytest.raises(InvalidAccountName):
        store.save_session(name, {"z_c0": "token"})


def test_cli_login_names_sessions_and_account_use_switches_them(tmp_config_dir):
    runner = CliRunner()
    first = "z_c0=one; _xsrf=x1; d_c0=d1"
    second = "z_c0=two; _xsrf=x2; d_c0=d2"

    assert runner.invoke(cli, ["login", "--account", "personal", "--cookie", first]).exit_code == 0
    assert runner.invoke(cli, ["login", "--account", "work", "--cookie", second]).exit_code == 0

    listed = runner.invoke(cli, ["account", "list"])
    assert listed.exit_code == 0
    assert "personal" in listed.output
    assert "work" in listed.output
    assert runner.invoke(cli, ["account", "use", "personal", "--backend", "session"]).exit_code == 0
    assert cookie_str_to_dict(get_cookie_string() or "")["z_c0"] == "one"


def test_cli_account_remove_deletes_only_selected_session(tmp_config_dir):
    runner = CliRunner()
    cookie = "z_c0=one; _xsrf=x; d_c0=d"
    runner.invoke(cli, ["login", "--account", "one", "--cookie", cookie])
    runner.invoke(cli, ["login", "--account", "two", "--cookie", cookie])

    removed = runner.invoke(cli, ["account", "remove", "two", "--backend", "session", "--yes"])

    assert removed.exit_code == 0
    assert [item.name for item in AccountStore(tmp_config_dir[0]).list("session")] == ["one"]


def test_cli_named_api_login_validates_then_saves_secret_in_keychain(tmp_config_dir, monkeypatch):
    secrets = MemorySecrets()
    monkeypatch.setattr("zhihu_cli.accounts._default_secret_store", lambda: secrets)
    completed = CompletedProcess(["zhihu-cli"], 0, '{"ok":true}\n', "")

    with patch("zhihu_cli.commands.auth.run_official", return_value=completed) as run:
        result = CliRunner().invoke(
            cli,
            ["login", "--api", "--account", "work"],
            input="api-secret\n",
        )

    assert result.exit_code == 0
    assert run.call_args.args[0] == ["auth", "status", "--verify"]
    assert run.call_args.kwargs["access_secret"] == "api-secret"
    store = AccountStore(tmp_config_dir[0], secret_store=secrets)
    assert store.active_name("api") == "work"
    assert store.active_api_secret() == "api-secret"
    assert "api-secret" not in (tmp_config_dir[0] / "accounts.json").read_text(encoding="utf-8")


def test_qrcode_login_can_be_saved_under_a_named_session(tmp_config_dir):
    cookie = "z_c0=qr; _xsrf=x; d_c0=d"
    with patch("zhihu_cli.commands.auth.qrcode_login", return_value=cookie), patch(
        "zhihu_cli.commands.auth._verify_cookies", return_value=True
    ):
        result = CliRunner().invoke(cli, ["login", "--qrcode", "--account", "mobile"])

    assert result.exit_code == 0
    store = AccountStore(tmp_config_dir[0], secret_store=MemorySecrets())
    assert store.active_name("session") == "mobile"
    assert store.active_session_cookies()["z_c0"] == "qr"


def test_global_account_option_uses_named_session_without_switching_default(tmp_config_dir):
    store = AccountStore(tmp_config_dir[0], secret_store=MemorySecrets())
    store.save_session("personal", {"z_c0": "one", "_xsrf": "x1", "d_c0": "d1"})
    store.save_session("work", {"z_c0": "two", "_xsrf": "x2", "d_c0": "d2"})

    with patch("zhihu_cli.commands.auth._verify_cookies", return_value=True):
        result = CliRunner().invoke(cli, ["--account", "personal", "login"])

    assert result.exit_code == 0
    assert store.active_name("session") == "work"
    assert "Already authenticated" in result.output


def test_unknown_named_session_never_falls_back_to_active_cookie(tmp_config_dir):
    AccountStore(tmp_config_dir[0], secret_store=MemorySecrets()).save_session(
        "work", {"z_c0": "two", "_xsrf": "x2", "d_c0": "d2"}
    )

    result = CliRunner().invoke(cli, ["--account", "missing", "status"])

    assert result.exit_code == 1
    assert "Not authenticated" in result.output


def test_global_account_option_selects_api_secret_without_changing_active(
    tmp_config_dir, tmp_path, monkeypatch
):
    secrets = MemorySecrets()
    monkeypatch.setattr("zhihu_cli.accounts._default_secret_store", lambda: secrets)
    store = AccountStore(tmp_config_dir[0], secret_store=secrets)
    store.save_api("personal", "secret-one")
    store.save_api("work", "secret-two")
    binary = tmp_path / "zhihu-cli"
    binary.write_text("binary", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("ZHIHU_OFFICIAL_CLI", str(binary))

    with patch("zhihu_cli.official.subprocess.run") as run:
        run.return_value = CompletedProcess([], 0, "ok\n", "")
        result = CliRunner().invoke(cli, ["--account", "personal", "api", "capabilities"])

    assert result.exit_code == 0
    assert run.call_args.kwargs["env"]["ZHIHU_ACCESS_SECRET"] == "secret-one"
    assert store.active_name("api") == "work"
