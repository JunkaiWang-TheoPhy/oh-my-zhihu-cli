"""Integration helpers for the official Zhihu Open Platform CLI."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .accounts import active_api_secret


class OfficialCliError(RuntimeError):
    """Raised when the official CLI cannot be launched."""


def get_official_cli_path() -> Path:
    """Return the configured official CLI path for the current platform."""
    override = os.environ.get("ZHIHU_OFFICIAL_CLI")
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "zhihu-cli"
            / "current"
            / "zhihu-cli"
        )
    if system == "Windows":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / "zhihu-cli" / "current" / "zhihu-cli.exe"
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "zhihu-cli" / "current" / "zhihu-cli"


def run_official(
    args: Sequence[str],
    *,
    input_text: str | None = None,
    timeout: float = 60,
    access_secret: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the official CLI without exposing credentials in arguments or logs."""
    binary = get_official_cli_path()
    if not binary.is_file():
        raise OfficialCliError(
            f"Official zhihu-cli is not installed at {binary}. "
            "Install the official Zhihu Skill first."
        )
    if not os.access(binary, os.X_OK):
        raise OfficialCliError(f"Official zhihu-cli is not executable: {binary}")

    try:
        environment = os.environ.copy()
        named_secret = access_secret or active_api_secret()
        if named_secret:
            environment["ZHIHU_ACCESS_SECRET"] = named_secret
        return subprocess.run(
            [str(binary), *args],
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise OfficialCliError("Official zhihu-cli timed out") from exc
    except OSError as exc:
        raise OfficialCliError(f"Could not launch official zhihu-cli: {exc}") from exc
