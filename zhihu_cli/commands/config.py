"""Local settings for backend priority and terminal language."""

from __future__ import annotations

import click

from .. import config as config_module
from ..display import print_error, print_success
from ..routing import load_settings, save_settings


@click.group("config")
def config() -> None:
    """View or change local zhihu-cli settings."""


@config.command("show")
def show() -> None:
    """Show backend priority and language."""
    settings = load_settings()
    click.echo(f"priority={settings['priority']}")
    click.echo(f"language={settings['language']}")
    click.echo(f"file={config_module.CONFIG_FILE}")


@config.command("set")
@click.argument("key", type=click.Choice(["priority", "language"]))
@click.argument("value")
def set_value(key: str, value: str) -> None:
    """Set PRIORITY (session/api) or LANGUAGE (zh/en)."""
    if key == "priority" and value not in {"session", "api"}:
        print_error("priority must be session or api")
        raise click.exceptions.Exit(2)
    if key == "language" and value not in {"zh", "en"}:
        print_error("language must be zh or en")
        raise click.exceptions.Exit(2)
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    print_success(f"Saved {key}={value}")
