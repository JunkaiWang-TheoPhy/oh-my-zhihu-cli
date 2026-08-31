"""Tests for the full-screen terminal console model."""

from __future__ import annotations

from unittest.mock import patch

from zhihu_cli.console import ConsoleState, _execute_selected, render_frame


def test_console_has_fixed_workbench_regions():
    state = ConsoleState()
    frame = render_frame(state, width=100, height=28)

    assert "知乎工作台" in frame
    assert "浏览" in frame
    assert "写作" in frame
    assert "命令" in frame
    assert "Session" in frame
    assert "Official API" in frame


def test_console_navigation_changes_active_workspace():
    state = ConsoleState()
    state.move_to(2)

    assert state.active_name == "热榜"
    assert state.active_command == "hot"


def test_console_command_line_builds_existing_cli_command():
    state = ConsoleState(command_line="search Python --api")

    assert state.command_args() == ["search", "Python", "--api"]


def test_console_executes_in_process_and_keeps_output_in_state():
    state = ConsoleState(command_line="status", readonly=True, backend="session")
    with patch("zhihu_cli.cli.cli") as command:
        command.main.return_value = None
        _execute_selected(state)

    command.main.assert_called_once_with(
        ["--readonly", "--session", "status"], standalone_mode=False
    )
    assert state.messages[0] == "欢迎来到知乎工作台。"
    assert "$ --readonly --session status" in state.messages
    assert "命令已执行，无输出。" in state.messages


def test_home_enter_keeps_the_dashboard_quiet():
    state = ConsoleState()
    _execute_selected(state)

    assert all("首页没有默认命令" not in message for message in state.messages)


def test_bare_write_command_never_reaches_click():
    state = ConsoleState(active_index=4, command_line="pin")
    with patch("zhihu_cli.cli.cli") as command:
        _execute_selected(state)

    command.main.assert_not_called()
    assert all("Missing parameter" not in message for message in state.messages)


def test_console_shows_active_accounts_and_has_account_workspace():
    state = ConsoleState(session_account="personal", api_account="research")
    state.move_to(6)

    frame = render_frame(state, width=100, height=32)

    assert state.active_name == "账号"
    assert state.active_command == "account list"
    assert "Session:personal" in frame
    assert "API:research" in frame


def test_console_account_override_is_forwarded_to_embedded_cli():
    state = ConsoleState(command_line="status", account="personal")
    with patch("zhihu_cli.cli.cli") as command:
        command.main.return_value = None
        _execute_selected(state)

    command.main.assert_called_once_with(
        ["--account", "personal", "status"], standalone_mode=False
    )


def test_console_has_help_workspace_that_opens_guidance():
    state = ConsoleState()
    state.move_to(7)

    assert state.active_name == "帮助"
    assert state.active_command == "guidance"
