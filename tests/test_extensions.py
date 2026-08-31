"""Regression tests for the zhihu-cli extensions."""

from __future__ import annotations

from pathlib import Path

import requests
from click.testing import CliRunner

from zhihu_cli.cli import cli
from zhihu_cli.client import ZhihuClient
from zhihu_cli.config import COOKIE_FILE, get_cookie_file


def test_readonly_blocks_write_without_network():
    result = CliRunner().invoke(cli, ["--readonly", "pin", "不会发布"])
    assert result.exit_code != 0
    assert "read-only" in result.output.lower()


def test_new_writes_are_preview_only_by_default():
    answer = CliRunner().invoke(cli, ["answer-post", "123", "--content", "预览"])
    comment = CliRunner().invoke(cli, ["comment", "answer", "123", "预览"])
    assert answer.exit_code == 0
    assert comment.exit_code == 0
    assert "dry-run" in answer.output.lower()
    assert "dry-run" in comment.output.lower()


def test_dry_run_pin_does_not_require_authentication():
    result = CliRunner().invoke(cli, ["pin", "标题", "--dry-run"])
    assert result.exit_code == 0
    assert "no request" in result.output.lower()


def test_profile_paths_preserve_default_cookie_location():
    assert get_cookie_file("default") == COOKIE_FILE
    expected = Path.home() / ".zhihu-cli" / "profiles" / "work" / "cookies.json"
    assert get_cookie_file("work") == expected


def test_markdown_snapshot_diff_uses_real_id():
    from zhihu_cli.commands.backup import _load_snapshot

    before = Path("/tmp/zhihu-before.md")
    after = Path("/tmp/zhihu-after.md")
    before.write_text("## 1. 旧标题\n\n- ID：1\n", encoding="utf-8")
    after.write_text("## 1. 新标题\n\n- ID：1\n", encoding="utf-8")
    try:
        assert _load_snapshot(before)["1"]["title"] == "旧标题"
        assert _load_snapshot(after)["1"]["title"] == "新标题"
    finally:
        before.unlink(missing_ok=True)
        after.unlink(missing_ok=True)


class _Response:
    status_code = 200
    text = "{}"

    @staticmethod
    def json():
        return {"ok": True}


class _FlakyGet:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise requests.Timeout("temporary")
        return _Response()


def test_get_retry_is_bounded_and_idempotent():
    client = ZhihuClient({}, timeout=1, retries=1)
    session = _FlakyGet()
    client._session = session
    assert client._get("https://example.test") == {"ok": True}
    assert session.calls == 2
