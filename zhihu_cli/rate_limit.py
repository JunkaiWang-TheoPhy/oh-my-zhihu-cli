"""Persistent, conservative rate limiting for Zhihu query requests."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .accounts import active_account_name

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX
    msvcrt = None


@dataclass(frozen=True)
class RateLimitPolicy:
    """Conservative local policy for one query scope."""

    min_interval_seconds: float = 3.0
    window_seconds: float = 60.0
    max_requests: int = 10
    server_cooldown_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.min_interval_seconds) or self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be non-negative")
        if not math.isfinite(self.window_seconds) or self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.max_requests < 1:
            raise ValueError("max_requests must be positive")
        if (
            not math.isfinite(self.server_cooldown_seconds)
            or self.server_cooldown_seconds <= 0
        ):
            raise ValueError("server_cooldown_seconds must be positive")

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_interval_seconds": self.min_interval_seconds,
            "window_seconds": self.window_seconds,
            "max_requests": self.max_requests,
            "server_cooldown_seconds": self.server_cooldown_seconds,
        }


class RateLimitError(RuntimeError):
    """Raised when the local guard refuses to issue a query request."""

    code = "LOCAL_RATE_LIMIT"
    exit_code = 4

    def __init__(self, scope: str, reason: str, retry_after_seconds: float):
        self.scope = scope
        self.reason = reason
        self.retry_after_seconds = max(1, math.ceil(retry_after_seconds))
        messages = {
            "minimum_interval": "query requests must be spaced apart",
            "window": "the query request window is full",
            "server_cooldown": "the server rate-limit cooldown is active",
        }
        message = messages.get(reason, "the local query rate limit is active")
        super().__init__(
            f"{self.code}: {message}; "
            f"retry after {self.retry_after_seconds}s",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "local_guard",
            "code": self.code,
            "reason": self.reason,
            "scope": self.scope,
            "retry_after_seconds": self.retry_after_seconds,
            "message": str(self),
        }


class RateLimitStateError(RuntimeError):
    """Raised when the local state cannot be safely trusted."""


def default_rate_limit_path() -> Path:
    """Return the local state path without reading credentials or query data."""
    return config.CONFIG_DIR / "rate-limit.json"


def current_rate_scope(backend: str, endpoint: str) -> str:
    """Build a stable, credential-free scope for the active account/profile."""
    backend = getattr(backend, "value", backend)
    try:
        import click

        context = click.get_current_context(silent=True)
    except (ImportError, RuntimeError):
        context = None

    root_options = (context.find_root().obj or {}) if context else {}
    account = root_options.get("account")
    profile = root_options.get("profile", config.DEFAULT_PROFILE)
    if account:
        identity = f"account:{account}"
    elif profile != config.DEFAULT_PROFILE:
        identity = f"profile:{profile}"
    else:
        active_account = active_account_name(str(backend))
        identity = f"account:{active_account}" if active_account else f"profile:{profile}"
    return f"{backend}:{identity}:{endpoint}"


class RateLimiter:
    """Persist query reservations and cooldowns across CLI processes."""

    _STATE_VERSION = 1

    def __init__(
        self,
        state_path: Path | None = None,
        *,
        policy: RateLimitPolicy | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.path = Path(state_path) if state_path else default_rate_limit_path()
        self.policy = policy or RateLimitPolicy()
        self._clock = clock or time.time

    @contextmanager
    def _locked_state(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.path.with_name(f"{self.path.name}.lock")
            with lock_path.open("a+") as handle:
                lock_path.chmod(0o600)
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                elif msvcrt is not None:  # pragma: no cover - Windows path
                    handle.seek(0)
                    handle.write("0")
                    handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    elif msvcrt is not None:  # pragma: no cover - Windows path
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError as exc:
            raise RateLimitStateError(f"Cannot lock rate-limit state: {exc}") from exc

    def _empty_state(self) -> dict[str, Any]:
        return {"version": self._STATE_VERSION, "scopes": {}}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_state()
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RateLimitStateError("Rate-limit state is unreadable") from exc
        if (
            not isinstance(state, dict)
            or state.get("version") != self._STATE_VERSION
            or not isinstance(state.get("scopes"), dict)
        ):
            raise RateLimitStateError("Rate-limit state has an unsupported format")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        except OSError as exc:
            raise RateLimitStateError(f"Cannot save rate-limit state: {exc}") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _record(self, state: dict[str, Any], scope: str) -> dict[str, Any]:
        scopes = state["scopes"]
        record = scopes.get(scope)
        if record is None:
            record = {
                "requests": [],
                "cooldown_until": 0.0,
                "last_error": None,
                "last_error_at": None,
            }
            scopes[scope] = record
        if not isinstance(record, dict):
            raise RateLimitStateError("Rate-limit scope has an unsupported format")
        requests = record.get("requests", [])
        if not isinstance(requests, list):
            raise RateLimitStateError("Rate-limit request history has an unsupported format")
        try:
            timestamps = [float(value) for value in requests]
            record["cooldown_until"] = float(record.get("cooldown_until", 0.0))
        except (TypeError, ValueError) as exc:
            raise RateLimitStateError("Rate-limit timestamps are invalid") from exc
        if not all(math.isfinite(value) for value in timestamps + [record["cooldown_until"]]):
            raise RateLimitStateError("Rate-limit timestamps are invalid")
        record["requests"] = timestamps
        return record

    def _active_requests(self, record: dict[str, Any], now: float) -> list[float]:
        cutoff = now - self.policy.window_seconds
        return sorted(timestamp for timestamp in record["requests"] if timestamp >= cutoff)

    def acquire(self, scope: str) -> None:
        """Reserve one query slot or fail before the network operation."""
        now = float(self._clock())
        with self._locked_state():
            state = self._load()
            record = self._record(state, scope)
            requests = self._active_requests(record, now)
            record["requests"] = requests

            cooldown_wait = record["cooldown_until"] - now
            if cooldown_wait > 0:
                self._save(state)
                raise RateLimitError(scope, "server_cooldown", cooldown_wait)

            waits: list[tuple[str, float]] = []
            if requests:
                interval_wait = self.policy.min_interval_seconds - (now - requests[-1])
                if interval_wait > 0:
                    waits.append(("minimum_interval", interval_wait))
            if len(requests) >= self.policy.max_requests:
                window_wait = requests[0] + self.policy.window_seconds - now
                if window_wait > 0:
                    waits.append(("window", window_wait))
            if waits:
                reason, wait = max(waits, key=lambda item: item[1])
                self._save(state)
                raise RateLimitError(scope, reason, wait)

            record["requests"] = [*requests, now]
            record["cooldown_until"] = 0.0
            self._save(state)

    def record_success(self, scope: str) -> None:
        """Clear a prior remote error after a successful query."""
        now = float(self._clock())
        with self._locked_state():
            state = self._load()
            record = self._record(state, scope)
            record["last_error"] = None
            record["last_error_at"] = None
            if record["cooldown_until"] <= now:
                record["cooldown_until"] = 0.0
            self._save(state)

    def record_server_rate_limit(
        self,
        scope: str,
        cooldown_seconds: float | None = None,
    ) -> None:
        """Persist a server-side rate-limit cooldown without storing query text."""
        now = float(self._clock())
        duration = cooldown_seconds or self.policy.server_cooldown_seconds
        with self._locked_state():
            state = self._load()
            record = self._record(state, scope)
            record["cooldown_until"] = max(record["cooldown_until"], now + duration)
            record["last_error"] = "remote_rate_limit"
            record["last_error_at"] = now
            self._save(state)

    def _status_for_record(
        self,
        scope: str,
        record: dict[str, Any],
        now: float,
    ) -> dict[str, Any]:
        requests = self._active_requests(record, now)
        cooldown_wait = max(0.0, record["cooldown_until"] - now)
        interval_wait = 0.0
        if requests:
            interval_wait = max(
                0.0,
                self.policy.min_interval_seconds - (now - requests[-1]),
            )
        window_wait = 0.0
        if len(requests) >= self.policy.max_requests:
            window_wait = max(0.0, requests[0] + self.policy.window_seconds - now)
        next_allowed = max(cooldown_wait, interval_wait, window_wait)
        return {
            "scope": scope,
            "window_requests": len(requests),
            "max_requests": self.policy.max_requests,
            "window_seconds": self.policy.window_seconds,
            "min_interval_seconds": self.policy.min_interval_seconds,
            "cooldown_remaining_seconds": math.ceil(cooldown_wait),
            "next_allowed_in_seconds": math.ceil(next_allowed),
            "last_error": record.get("last_error"),
            "last_error_at": record.get("last_error_at"),
        }

    def status(self, scope: str | None = None) -> dict[str, Any]:
        """Return safe local status, omitting credentials and query content."""
        now = float(self._clock())
        with self._locked_state():
            state = self._load()
            if scope is not None:
                return self._status_for_record(scope, self._record(state, scope), now)
            result = []
            for name in sorted(state["scopes"]):
                result.append(self._status_for_record(name, self._record(state, name), now))
            return {"policy": self.policy.as_dict(), "scopes": result}


def is_remote_rate_limited(value: Any) -> bool:
    """Recognize a server rate-limit response without treating empty data as one."""
    def contains_rate_limit_code(text: str) -> bool:
        return bool(
            re.search(
                r"[\"']?(?:Code|code)[\"']?\s*[:=]\s*[\"']?30001[\"']?",
                text,
            )
        )

    if isinstance(value, dict):
        code = value.get("Code", value.get("code"))
        return str(code) == "30001"

    status_code = getattr(value, "status_code", None)
    if status_code == 429:
        return True

    if isinstance(value, BaseException):
        message = str(value)
        return contains_rate_limit_code(message) or bool(
            re.search(r"rate[- ]limit|rate limited", message, re.IGNORECASE)
        )

    stdout = getattr(value, "stdout", "") or ""
    stderr = getattr(value, "stderr", "") or ""
    combined = f"{stdout}\n{stderr}"
    if not getattr(value, "returncode", 0):
        return False
    return bool(
        contains_rate_limit_code(combined)
        or re.search(r"rate limit exceeded", combined, re.IGNORECASE)
    )


def run_limited(
    scope: str,
    operation: Callable[[], Any],
    *,
    limiter: RateLimiter | None = None,
) -> Any:
    """Reserve a slot, run one operation, and persist remote rate-limit feedback."""
    limiter = limiter or RateLimiter()
    limiter.acquire(scope)
    try:
        result = operation()
    except Exception as exc:
        if is_remote_rate_limited(exc):
            limiter.record_server_rate_limit(scope)
        raise
    if is_remote_rate_limited(result):
        limiter.record_server_rate_limit(scope)
    else:
        limiter.record_success(scope)
    return result
