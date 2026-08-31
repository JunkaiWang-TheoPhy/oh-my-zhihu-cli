"""Behavior tests for interactive CLI guidance."""

from click.testing import CliRunner

from zhihu_cli.cli import cli


def test_guidance_without_topic_shows_first_steps_and_topics():
    result = CliRunner().invoke(cli, ["guidance"])

    assert result.exit_code == 0
    assert "zhihu login --account personal --qrcode" in result.output
    assert "accounts" in result.output
    assert "backends" in result.output
    assert "tui" in result.output


def test_guidance_accounts_explains_named_login_switch_and_one_shot_override():
    result = CliRunner().invoke(cli, ["guidance", "accounts"])

    assert result.exit_code == 0
    assert "zhihu account list" in result.output
    assert "zhihu account use work --backend session" in result.output
    assert "zhihu --account personal search" in result.output


def test_guide_alias_and_chinese_topic_work():
    result = CliRunner().invoke(cli, ["guide", "账号"])

    assert result.exit_code == 0
    assert "多账号" in result.output
    assert "zhihu login --api --account research" in result.output


def test_unknown_guidance_topic_returns_actionable_error():
    result = CliRunner().invoke(cli, ["guidance", "unknown"])

    assert result.exit_code == 2
    assert "quickstart" in result.output
    assert "accounts" in result.output
