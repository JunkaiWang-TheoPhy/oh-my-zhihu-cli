"""Tests for the persistent query rate limiter."""

from __future__ import annotations

import json
from stat import S_IMODE
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from zhihu_cli.cli import cli
from zhihu_cli.rate_limit import (
    RateLimiter,
    RateLimitError,
    RateLimitPolicy,
    RateLimitStateError,
    current_rate_scope,
    run_limited,
)


class FakeClock:
    def __init__(self, value: float = 1_000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_minimum_interval_is_enforced(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=3),
        clock=clock,
    )

    limiter.acquire("session:profile:default:search")
    clock.advance(2.9)

    with pytest.raises(RateLimitError) as exc_info:
        limiter.acquire("session:profile:default:search")

    assert exc_info.value.code == "LOCAL_RATE_LIMIT"
    assert exc_info.value.reason == "minimum_interval"
    assert exc_info.value.retry_after_seconds > 0


def test_sliding_window_is_enforced(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=0, max_requests=3, window_seconds=60),
        clock=clock,
    )

    for _ in range(3):
        limiter.acquire("api:account:research:zhihu_search")

    with pytest.raises(RateLimitError) as exc_info:
        limiter.acquire("api:account:research:zhihu_search")

    assert exc_info.value.reason == "window"
    assert 0 < exc_info.value.retry_after_seconds <= 60


def test_server_rate_limit_sets_persistent_cooldown(tmp_path):
    clock = FakeClock()
    path = tmp_path / "rate-limit.json"
    limiter = RateLimiter(
        path,
        policy=RateLimitPolicy(min_interval_seconds=0, server_cooldown_seconds=120),
        clock=clock,
    )
    scope = "api:account:research:zhihu_search"

    limiter.acquire(scope)
    limiter.record_server_rate_limit(scope)

    status = limiter.status(scope)
    assert status["last_error"] == "remote_rate_limit"
    assert status["cooldown_remaining_seconds"] == 120

    other = RateLimiter(path, policy=limiter.policy, clock=clock)
    with pytest.raises(RateLimitError) as exc_info:
        other.acquire(scope)
    assert exc_info.value.reason == "server_cooldown"


def test_success_clears_previous_server_error_after_cooldown(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=0),
        clock=clock,
    )
    scope = "session:account:personal:search"

    limiter.acquire(scope)
    limiter.record_server_rate_limit(scope)
    clock.advance(121)
    limiter.acquire(scope)
    limiter.record_success(scope)

    status = limiter.status(scope)
    assert status["last_error"] is None
    assert status["window_requests"] == 1


def test_rate_limit_state_is_separate_per_account_scope(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=3),
        clock=clock,
    )

    limiter.acquire("session:account:personal:search")
    limiter.acquire("session:account:work:search")

    assert limiter.status("session:account:personal:search")["window_requests"] == 1
    assert limiter.status("session:account:work:search")["window_requests"] == 1


def test_current_rate_scope_uses_explicit_account_without_reading_credentials():
    @click.command()
    @click.pass_context
    def probe(ctx):
        ctx.ensure_object(dict)
        ctx.obj.update({"account": "research", "profile": "default"})
        click.echo(current_rate_scope("api", "zhihu_search"))

    result = CliRunner().invoke(probe)

    assert result.exit_code == 0
    assert result.output.strip() == "api:account:research:zhihu_search"


def test_invalid_state_fails_closed(tmp_path):
    path = tmp_path / "rate-limit.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(RateLimitStateError):
        RateLimiter(path).acquire("session:profile:default:search")


def test_state_file_is_private_and_contains_no_query_text(tmp_path):
    path = tmp_path / "rate-limit.json"
    limiter = RateLimiter(path)

    limiter.acquire("api:account:research:zhihu_search")

    assert S_IMODE(path.stat().st_mode) == 0o600
    assert "query" not in path.read_text(encoding="utf-8").lower()


def test_run_limited_records_remote_rate_limit_without_retrying(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=0),
        clock=clock,
    )
    result = CompletedProcess(
        ["zhihu-cli"],
        4,
        stdout='{"Code":30001,"Message":"rate limit exceeded"}\n',
        stderr="",
    )

    returned = run_limited(
        "api:account:research:zhihu_search",
        lambda: result,
        limiter=limiter,
    )

    assert returned is result
    assert limiter.status("api:account:research:zhihu_search")["last_error"] == (
        "remote_rate_limit"
    )

    called = False

    def should_not_run():
        nonlocal called
        called = True
        return result

    with pytest.raises(RateLimitError):
        run_limited(
            "api:account:research:zhihu_search",
            should_not_run,
            limiter=limiter,
        )
    assert called is False


def test_run_limited_records_rate_limit_code_in_exception(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(
        tmp_path / "rate-limit.json",
        policy=RateLimitPolicy(min_interval_seconds=0),
        clock=clock,
    )
    scope = "session:account:personal:zhihu_search"

    def fail_with_remote_response():
        raise RuntimeError('API request failed: {"Code":30001}')

    with pytest.raises(RuntimeError, match="30001"):
        run_limited(scope, fail_with_remote_response, limiter=limiter)

    assert limiter.status(scope)["last_error"] == "remote_rate_limit"


def test_session_search_surfaces_local_guard_before_client_query(saved_cookies):
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    blocked = RateLimitError(
        "session:profile:default:zhihu_search",
        "minimum_interval",
        2,
    )

    with patch("zhihu_cli.client.ZhihuClient", return_value=client), patch(
        "zhihu_cli.commands.content.run_limited", side_effect=blocked
    ) as run:
        result = CliRunner().invoke(cli, ["--session", "search", "Python"])

    assert result.exit_code == RateLimitError.exit_code
    assert "LOCAL_RATE_LIMIT" in result.output
    run.assert_called_once()
    client.search.assert_not_called()


def test_session_search_emits_structured_guard_error_for_json(saved_cookies):
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    blocked = RateLimitError(
        "session:profile:default:zhihu_search",
        "window",
        30,
    )

    with patch("zhihu_cli.client.ZhihuClient", return_value=client), patch(
        "zhihu_cli.commands.content.run_limited", side_effect=blocked
    ):
        result = CliRunner().invoke(
            cli,
            ["--session", "search", "Python", "--json"],
        )

    assert result.exit_code == RateLimitError.exit_code
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "LOCAL_RATE_LIMIT"
    assert payload["error"]["retry_after_seconds"] == 30


def test_session_search_preserves_remote_rate_limit_exit_code_for_json(saved_cookies):
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    remote = {"Code": 30001, "Message": "rate limit exceeded"}

    with patch("zhihu_cli.client.ZhihuClient", return_value=client), patch(
        "zhihu_cli.commands.content.run_limited", return_value=remote
    ):
        result = CliRunner().invoke(
            cli,
            ["--session", "search", "Python", "--json"],
        )

    assert result.exit_code == RateLimitError.exit_code
    assert json.loads(result.output) == remote


def test_rate_limit_status_command_is_local_json(tmp_config_dir):
    result = CliRunner().invoke(cli, ["rate-limit", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["policy"]["min_interval_seconds"] == 3
    assert payload["policy"]["max_requests"] == 10
    assert payload["scopes"] == []


def test_search_limit_has_official_safe_bound():
    result = CliRunner().invoke(cli, ["search", "Python", "--limit", "11"])

    assert result.exit_code == 2
    assert "1" in result.output and "10" in result.output


def test_official_search_receives_rate_scope(tmp_config_dir):
    completed = CompletedProcess(["zhihu-cli"], 0, stdout="{}\n", stderr="")

    with patch("zhihu_cli.routing.api_configured", return_value=True), patch(
        "zhihu_cli.commands.content.run_official", return_value=completed
    ) as run:
        result = CliRunner().invoke(cli, ["--api", "search", "Python"])

    assert result.exit_code == 0
    assert run.call_args.kwargs["rate_scope"] == "api:profile:default:zhihu_search"


def test_direct_official_search_receives_rate_scope(tmp_config_dir):
    completed = CompletedProcess(["zhihu-cli"], 0, stdout="{}\n", stderr="")

    with patch("zhihu_cli.commands.official.run_official", return_value=completed) as run:
        result = CliRunner().invoke(
            cli,
            ["api", "search", "zhihu", "--query", "Python"],
        )

    assert result.exit_code == 0
    assert run.call_args.kwargs["rate_scope"] == "api:profile:default:zhihu_search"


def test_invalid_direct_official_search_count_does_not_reserve_rate_slot(tmp_config_dir):
    completed = CompletedProcess(["zhihu-cli"], 2, stdout="", stderr="invalid count")

    with patch("zhihu_cli.commands.official.run_official", return_value=completed) as run:
        result = CliRunner().invoke(
            cli,
            ["api", "search", "zhihu", "--count", "20"],
        )

    assert result.exit_code == 2
    assert "rate_scope" not in run.call_args.kwargs


def test_valid_direct_official_global_search_uses_separate_rate_scope(tmp_config_dir):
    completed = CompletedProcess(["zhihu-cli"], 0, stdout="{}\n", stderr="")

    with patch("zhihu_cli.commands.official.run_official", return_value=completed) as run:
        result = CliRunner().invoke(
            cli,
            ["api", "search", "global", "--count", "20"],
        )

    assert result.exit_code == 0
    assert run.call_args.kwargs["rate_scope"] == "api:profile:default:global_search"
