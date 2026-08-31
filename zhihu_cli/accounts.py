"""Named account storage for Session cookies and Official API secrets."""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import config


class AccountError(RuntimeError):
    """Base error for account management."""


class InvalidAccountName(AccountError):
    """Raised when an account name is unsafe or unusable."""


class SecretStore(Protocol):
    def set(self, name: str, secret: str) -> None: ...
    def get(self, name: str) -> str | None: ...
    def delete(self, name: str) -> None: ...


@dataclass(frozen=True)
class AccountInfo:
    name: str
    backend: str
    active: bool


class MacOSKeychainSecretStore:
    """Store named API secrets in the macOS login keychain."""

    service = "oh-my-zhihu-cli.api"

    def set(self, name: str, secret: str) -> None:
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                self.service,
                "-a",
                name,
                "-w",
            ],
            input=secret + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AccountError(result.stderr.strip() or "Failed to save API secret in Keychain")

    def get(self, name: str) -> str | None:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", self.service, "-a", name, "-w"],
            text=True,
            capture_output=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def delete(self, name: str) -> None:
        subprocess.run(
            ["security", "delete-generic-password", "-s", self.service, "-a", name],
            text=True,
            capture_output=True,
            check=False,
        )


class UnsupportedSecretStore:
    def set(self, name: str, secret: str) -> None:
        raise AccountError("Named Official API accounts require the macOS Keychain")

    def get(self, name: str) -> str | None:
        return None

    def delete(self, name: str) -> None:
        return None


class AccountStore:
    """Persist account metadata and Session cookies under one config root."""

    def __init__(self, root: Path, *, secret_store: SecretStore | None = None):
        self.root = Path(root)
        self.path = self.root / "accounts.json"
        self.legacy_cookie_file = self.root / "cookies.json"
        self.secret_store = secret_store or _default_secret_store()

    def _blank(self) -> dict:
        return {
            "version": 1,
            "active": {"session": None, "api": None},
            "session": {},
            "api": {},
        }

    def _load(self) -> dict:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise AccountError(f"Invalid account registry: {exc}") from exc
            if isinstance(data, dict):
                return data
        data = self._blank()
        if self.legacy_cookie_file.exists():
            try:
                legacy = json.loads(self.legacy_cookie_file.read_text(encoding="utf-8"))
                cookies = legacy.get("cookies", {})
            except (OSError, json.JSONDecodeError):
                cookies = {}
            if isinstance(cookies, dict) and cookies:
                data["session"]["default"] = {"cookies": cookies}
                data["active"]["session"] = "default"
                self._save(data)
        return data

    def _save(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.path.chmod(0o600)

    def save_session(self, name: str, cookies: dict[str, str]) -> None:
        name = _validate_name(name)
        data = self._load()
        data["session"][name] = {"cookies": dict(cookies)}
        data["active"]["session"] = name
        self._save(data)
        self._materialize_session(data)

    def save_api(self, name: str, secret: str) -> None:
        name = _validate_name(name)
        if not secret.strip():
            raise AccountError("Access Secret cannot be empty")
        self.secret_store.set(name, secret.strip())
        data = self._load()
        data["api"][name] = {"credential_store": "system"}
        data["active"]["api"] = name
        self._save(data)

    def list(self, backend: str | None = None) -> list[AccountInfo]:
        data = self._load()
        backends = (backend,) if backend else ("session", "api")
        result = []
        for item_backend in backends:
            _validate_backend(item_backend)
            active = data["active"].get(item_backend)
            result.extend(
                AccountInfo(name=name, backend=item_backend, active=name == active)
                for name in sorted(data[item_backend])
            )
        return result

    def use(self, name: str, backend: str) -> None:
        name = _validate_name(name)
        _validate_backend(backend)
        data = self._load()
        if name not in data[backend]:
            raise AccountError(f"Unknown {backend} account: {name}")
        data["active"][backend] = name
        self._save(data)
        if backend == "session":
            self._materialize_session(data)

    def remove(self, name: str, backend: str) -> None:
        name = _validate_name(name)
        _validate_backend(backend)
        data = self._load()
        if name not in data[backend]:
            raise AccountError(f"Unknown {backend} account: {name}")
        del data[backend][name]
        if backend == "api":
            self.secret_store.delete(name)
        if data["active"].get(backend) == name:
            data["active"][backend] = sorted(data[backend])[0] if data[backend] else None
        self._save(data)
        if backend == "session":
            self._materialize_session(data)

    def active_name(self, backend: str) -> str | None:
        _validate_backend(backend)
        return self._load()["active"].get(backend)

    def active_session_cookies(self) -> dict[str, str]:
        data = self._load()
        name = data["active"].get("session")
        if not name:
            return {}
        return dict(data["session"].get(name, {}).get("cookies", {}))

    def session_cookies(self, name: str) -> dict[str, str]:
        name = _validate_name(name)
        return dict(self._load()["session"].get(name, {}).get("cookies", {}))

    def active_api_secret(self) -> str | None:
        name = self.active_name("api")
        return self.secret_store.get(name) if name else None

    def api_secret(self, name: str) -> str | None:
        name = _validate_name(name)
        return self.secret_store.get(name) if name in self._load()["api"] else None

    def _materialize_session(self, data: dict) -> None:
        name = data["active"].get("session")
        if not name:
            if self.legacy_cookie_file.exists():
                self.legacy_cookie_file.unlink()
            return
        cookies = data["session"].get(name, {}).get("cookies", {})
        self.root.mkdir(parents=True, exist_ok=True)
        self.legacy_cookie_file.write_text(
            json.dumps({"cookies": cookies}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.legacy_cookie_file.chmod(0o600)


def _default_secret_store() -> SecretStore:
    return MacOSKeychainSecretStore() if platform.system() == "Darwin" else UnsupportedSecretStore()


def _validate_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > 64 or name in {".", ".."} or any(char in name for char in "/\\"):
        raise InvalidAccountName(
            "Account name must be 1-64 characters and cannot contain path separators"
        )
    if any(ord(char) < 32 for char in name):
        raise InvalidAccountName("Account name cannot contain control characters")
    return name


def _validate_backend(backend: str) -> None:
    if backend not in {"session", "api"}:
        raise AccountError(f"Unknown backend: {backend}")


def get_account_store() -> AccountStore:
    return AccountStore(config.CONFIG_DIR)


def active_account_name(backend: str) -> str | None:
    return get_account_store().active_name(backend)


def active_api_secret() -> str | None:
    store = get_account_store()
    requested = context_account_name()
    return store.api_secret(requested) if requested else store.active_api_secret()


def context_account_name() -> str | None:
    try:
        import click

        context = click.get_current_context(silent=True)
        root = context.find_root() if context else None
        return (root.obj or {}).get("account") if root else None
    except RuntimeError:
        return None
