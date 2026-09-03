"""Built-in, offline guidance for common zhihu-cli workflows."""

from __future__ import annotations

import click

TOPIC_ALIASES = {
    "quickstart": "quickstart",
    "start": "quickstart",
    "开始": "quickstart",
    "入门": "quickstart",
    "accounts": "accounts",
    "account": "accounts",
    "账号": "accounts",
    "多账号": "accounts",
    "backends": "backends",
    "backend": "backends",
    "后端": "backends",
    "tui": "tui",
    "工作台": "tui",
    "safety": "safety",
    "readonly": "safety",
    "安全": "safety",
    "只读": "safety",
}

GUIDES = {
    "quickstart": """快速开始 / Quick start

1. 登录一个 Session 账号：
   zhihu login --account personal --qrcode
2. 或登录官方 API：
   zhihu login --api --account research
3. 查看当前配置：
   zhihu account list
   zhihu config show
4. 开始使用：
   zhihu feed
   zhihu search "关键词"
   zhihu-tui

继续查看：zhihu guidance accounts|backends|tui|safety
""",
    "accounts": """多账号 / Multiple accounts

登录：
  zhihu login --account personal --qrcode
  zhihu login --account work --cookie "z_c0=...; _xsrf=...; d_c0=..."
  zhihu login --api --account research

管理：
  zhihu account list
  zhihu account current
  zhihu account use work --backend session
  zhihu account use research --backend api
  zhihu account remove work --backend session

单次覆盖，不改变默认账号：
  zhihu --account personal search "关键词"
  zhihu --account research api me contents --type all --limit 20
""",
    "backends": """后端路由 / Backend routing

Session：草稿、发布、互动和网页端数据。
Official API：公开搜索、本人数据、知识库和额度。

  zhihu config set priority session
  zhihu config set priority api
  zhihu --session search "关键词"
  zhihu --api search "关键词"
  zhihu-api capabilities
""",
    "tui": """终端工作台 / TUI

  zhihu-tui
  zhihu-tui --account personal
  zhihu-tui --readonly

快捷键：↑/↓ 或 j/k 导航，1-8 切换工作区，: 输入命令，Enter 执行，q 退出。
普通 CLI 始终保留，例如 zhihu feed、zhihu drafts、zhihu account list。
""",
    "safety": """安全与只读模式 / Safety

  zhihu --readonly feed
  zhihu --readonly search "关键词"
  zhihu-tui --readonly
  zhihu rate-limit status --json

只读模式会拦截发布、互动、删除和知识库上传。Session Cookie 存在权限为 0600
的本地账号文件；命名 API Secret 存入 macOS Keychain，不写入命令参数或配置文件。
搜索命令还会按账号/profile执行本地硬限流；收到限流错误时不要立即重试。
""",
}


@click.command()
@click.argument("topic", required=False)
def guidance(topic: str | None) -> None:
    """Show offline guidance for setup, accounts, backends, TUI, and safety."""
    selected = TOPIC_ALIASES.get((topic or "quickstart").lower())
    if not selected:
        choices = "quickstart, accounts, backends, tui, safety"
        raise click.UsageError(f"Unknown guidance topic: {topic}. Available: {choices}")
    click.echo(GUIDES[selected].strip())
