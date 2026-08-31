"""Backend discovery and selection for overlapping Zhihu capabilities."""

from __future__ import annotations

import json
from enum import Enum

from . import config as config_module
from .auth import get_saved_cookie_string
from .official import OfficialCliError, run_official


class Backend(str, Enum):
    SESSION = "session"
    API = "api"


class BackendUnavailable(RuntimeError):
    """Raised when neither supported Zhihu backend is configured."""


def load_settings() -> dict[str, str]:
    defaults = {"language": "zh", "priority": Backend.SESSION.value}
    if not config_module.CONFIG_FILE.exists():
        return defaults
    try:
        data = json.loads(config_module.CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    defaults.update({key: str(value) for key, value in data.items() if key in defaults})
    if defaults["language"] not in {"zh", "en"}:
        defaults["language"] = "zh"
    if defaults["priority"] not in {Backend.SESSION.value, Backend.API.value}:
        defaults["priority"] = Backend.SESSION.value
    return defaults


def save_settings(settings: dict[str, str]) -> None:
    config_module.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config_module.CONFIG_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def session_configured() -> bool:
    return bool(get_saved_cookie_string())


def api_configured() -> bool:
    try:
        return run_official(["auth", "status"], timeout=5).returncode == 0
    except OfficialCliError:
        return False


def choose_backend(requested: str | None, settings: dict[str, str] | None = None) -> Backend:
    if requested:
        try:
            backend = Backend(requested)
        except ValueError as exc:
            raise BackendUnavailable(f"Unknown backend: {requested}") from exc
        if backend is Backend.SESSION and not session_configured():
            raise BackendUnavailable("Session backend is not configured")
        if backend is Backend.API and not api_configured():
            raise BackendUnavailable("Official API backend is not configured")
        return backend

    settings = settings or load_settings()
    available = {
        Backend.SESSION: session_configured(),
        Backend.API: api_configured(),
    }
    preferred = Backend(settings["priority"])
    for backend in (preferred, *[item for item in Backend if item is not preferred]):
        if available[backend]:
            return backend
    raise BackendUnavailable("Neither Session nor Official API backend is configured")


def first_run_guidance(language: str = "zh") -> str:
    if language == "en":
        return (
            "First-time setup: configure a Web Session with `zhihu login --qrcode` "
            "or configure the Official API with `zhihu login --api`. "
            "If the official CLI is missing, install the Zhihu CLI Skill first. "
            "Use `zhihu config set priority session|api` to choose the default.\n"
            "首次配置：使用 `zhihu login --qrcode` 配置 Web Session，或使用 "
            "`zhihu login --api` 配置官方 API；官方 CLI 未安装时请先安装知乎 CLI Skill。"
        )
    return (
        "首次配置：使用 `zhihu login --qrcode` 配置 Web Session，或使用 "
        "`zhihu login --api` 配置官方 API；可用 `zhihu config set priority session|api` "
        "指定默认后端；官方 CLI 未安装时请先安装知乎 CLI Skill。\n"
        "First-time setup: use `zhihu login --qrcode` for Web Session or "
        "`zhihu login --api` for the Official API; install the Zhihu CLI Skill first if needed."
    )
