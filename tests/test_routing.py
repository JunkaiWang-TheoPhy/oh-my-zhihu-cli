"""Tests for session/API backend selection and first-run guidance."""

from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from zhihu_cli.cli import cli
from zhihu_cli.routing import Backend, choose_backend, load_settings


def test_session_wins_by_default_when_both_backends_are_configured(tmp_path):
    settings = {"priority": "session", "language": "zh"}
    with patch("zhihu_cli.routing.session_configured", return_value=True), patch(
        "zhihu_cli.routing.api_configured", return_value=True
    ):
        assert choose_backend(None, settings) == Backend.SESSION


def test_explicit_backend_overrides_configured_priority(tmp_path):
    settings = {"priority": "session", "language": "zh"}
    with patch("zhihu_cli.routing.session_configured", return_value=True), patch(
        "zhihu_cli.routing.api_configured", return_value=True
    ):
        assert choose_backend("api", settings) == Backend.API


def test_missing_backends_show_bilingual_first_run_guidance():
    runner = CliRunner()
    with patch("zhihu_cli.routing.session_configured", return_value=False), patch(
        "zhihu_cli.routing.api_configured", return_value=False
    ):
        result = runner.invoke(cli, ["search", "Python"])

    assert result.exit_code != 0
    assert "首次配置" in result.output
    assert "First-time setup" in result.output
    assert "login --qrcode" in result.output
    assert "login --api" in result.output


def test_config_set_priority_persists(tmp_path, monkeypatch):
    config_file = tmp_path / "settings.json"
    monkeypatch.setattr("zhihu_cli.config.CONFIG_FILE", config_file)
    result = CliRunner().invoke(cli, ["config", "set", "priority", "api"])

    assert result.exit_code == 0
    assert json.loads(config_file.read_text()) == {"language": "zh", "priority": "api"}
    assert load_settings() == {"language": "zh", "priority": "api"}


def test_search_api_flag_forces_official_backend():
    completed = type("Result", (), {"returncode": 0, "stdout": "{}\n", "stderr": ""})()
    with patch("zhihu_cli.routing.api_configured", return_value=True), patch(
        "zhihu_cli.commands.content.run_official", return_value=completed
    ) as run:
        result = CliRunner().invoke(cli, ["search", "Python", "--api"])

    assert result.exit_code == 0
    assert run.call_args.args[0][:2] == ["search", "zhihu"]


def test_root_api_flag_forces_official_backend():
    completed = type("Result", (), {"returncode": 0, "stdout": "{}\n", "stderr": ""})()
    with patch("zhihu_cli.routing.api_configured", return_value=True), patch(
        "zhihu_cli.commands.content.run_official", return_value=completed
    ) as run:
        result = CliRunner().invoke(cli, ["--api", "search", "Python"])

    assert result.exit_code == 0
    assert run.call_args.args[0][:2] == ["search", "zhihu"]
