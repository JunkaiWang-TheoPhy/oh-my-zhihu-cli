"""Safety tests for the global read-only mode."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from zhihu_cli.cli import cli


@pytest.mark.parametrize("flag", ["--readonly", "--read-only"])
@pytest.mark.parametrize(
    "command_args",
    [
        ["ask", "标题"],
        ["pin", "标题"],
        ["article", "标题", "正文"],
        ["vote", "123"],
        ["follow-question", "123"],
        ["delete-question", "123", "--yes"],
        ["delete-pin", "123", "--yes"],
        ["delete-article", "123", "--yes"],
    ],
)
def test_readonly_blocks_mutations_before_client_creation(flag, command_args):
    """Read-only mode must block every remote mutation before auth/client setup."""
    with patch("zhihu_cli.commands.interact._get_client") as get_client:
        result = CliRunner().invoke(cli, [flag, *command_args])

    assert result.exit_code != 0
    assert "read-only mode" in result.output.lower()
    assert "not authenticated" not in result.output.lower()
    get_client.assert_not_called()


def test_readonly_allows_read_only_commands(tmp_path, monkeypatch):
    """The global guard must not block local/read-only commands."""
    config_dir = tmp_path / ".zhihu-cli"
    config_dir.mkdir()
    monkeypatch.setattr("zhihu_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("zhihu_cli.config.COOKIE_FILE", config_dir / "cookies.json")
    monkeypatch.setattr("zhihu_cli.auth.CONFIG_DIR", config_dir)
    monkeypatch.setattr("zhihu_cli.auth.COOKIE_FILE", config_dir / "cookies.json")

    result = CliRunner().invoke(cli, ["--readonly", "status"])

    assert result.exit_code == 1
    assert "not authenticated" in result.output.lower()
    assert "read-only mode" not in result.output.lower()
