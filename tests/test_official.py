"""Tests for the official Zhihu Open Platform CLI backend."""

from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from zhihu_cli.cli import cli
from zhihu_cli.official import get_official_cli_path, run_official
from zhihu_cli.rate_limit import RateLimiter


def _combined_output(result):
    return result.output + getattr(result, "stderr", "")


def test_official_cli_path_prefers_environment_override(monkeypatch, tmp_path):
    expected = tmp_path / "zhihu-cli"
    monkeypatch.setenv("ZHIHU_OFFICIAL_CLI", str(expected))

    assert get_official_cli_path() == expected


def test_api_command_forwards_arguments_and_shows_scope_prompt():
    completed = CompletedProcess(
        ["zhihu-cli"], 0, stdout='{"Code":0}\n', stderr="",
    )
    with patch("zhihu_cli.commands.official.run_official", return_value=completed) as run:
        result = CliRunner().invoke(
            cli, ["api", "search", "zhihu", "--query", "量子引力"],
        )

    assert result.exit_code == 0
    assert "Official API" in _combined_output(result)
    assert run.call_args.args[0] == ["search", "zhihu", "--query", "量子引力"]


def test_api_help_is_forwarded():
    completed = CompletedProcess(["zhihu-cli"], 0, stdout="official help\n", stderr="")
    with patch("zhihu_cli.commands.official.run_official", return_value=completed) as run:
        result = CliRunner().invoke(cli, ["api", "--help"])

    assert result.exit_code == 0
    assert "official help\n" in result.output
    run.assert_called_once_with(["--help"], timeout=60.0)


def test_api_login_passes_secret_via_stdin_without_echoing_it():
    completed = CompletedProcess(
        ["zhihu-cli"], 0, stdout='{"ok":true}\n', stderr="",
    )
    with patch("zhihu_cli.commands.auth.run_official", return_value=completed) as run:
        result = CliRunner().invoke(cli, ["login", "--api"], input="secret-value\n")

    assert result.exit_code == 0
    assert "secret-value" not in _combined_output(result)
    assert "API" in _combined_output(result)
    assert run.call_args.args[0] == ["auth", "set", "--secret-stdin"]
    assert run.call_args.kwargs["input_text"] == "secret-value"


def test_readonly_blocks_official_knowledge_upload(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")

    with patch("zhihu_cli.commands.official.run_official") as run:
        result = CliRunner().invoke(
            cli,
            ["--readonly", "api", "knowledge", "upload", "--file", str(source)],
        )

    assert result.exit_code != 0
    assert "read-only" in _combined_output(result).lower()
    run.assert_not_called()


def test_named_api_account_is_injected_through_environment_not_arguments(tmp_path, monkeypatch):
    binary = tmp_path / "zhihu-cli"
    binary.write_text("binary", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("ZHIHU_OFFICIAL_CLI", str(binary))

    with patch("zhihu_cli.official.active_api_secret", return_value="named-secret"), patch(
        "zhihu_cli.official.subprocess.run"
    ) as run:
        run.return_value = CompletedProcess([], 0, "ok", "")
        run_official(["hot"])

    command = run.call_args.args[0]
    environment = run.call_args.kwargs["env"]
    assert "named-secret" not in command
    assert environment["ZHIHU_ACCESS_SECRET"] == "named-secret"


def test_official_rate_limit_response_starts_local_cooldown(tmp_config_dir, tmp_path, monkeypatch):
    binary = tmp_path / "zhihu-cli"
    binary.write_text("binary", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("ZHIHU_OFFICIAL_CLI", str(binary))
    response = CompletedProcess(
        [str(binary)],
        4,
        stdout='{"Code":30001,"Message":"rate limit exceeded"}\n',
        stderr="",
    )
    scope = "api:profile:default:zhihu_search"

    with patch("zhihu_cli.official.subprocess.run", return_value=response):
        returned = run_official(["search", "zhihu"], rate_scope=scope)

    assert returned is response
    assert RateLimiter().status(scope)["last_error"] == "remote_rate_limit"
