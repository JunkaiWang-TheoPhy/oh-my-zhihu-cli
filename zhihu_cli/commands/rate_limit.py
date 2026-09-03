"""Local rate-limit inspection commands."""

from __future__ import annotations

import json

import click

from ..display import print_error, print_info
from ..rate_limit import RateLimiter, RateLimitStateError


@click.group("rate-limit")
def rate_limit() -> None:
    """Inspect the local query rate-limit guard."""


@rate_limit.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output JSON")
def status(as_json: bool) -> None:
    """Show local query limits and per-account reservations."""
    try:
        payload = RateLimiter().status()
    except RateLimitStateError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc

    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    policy = payload["policy"]
    click.echo("Query rate-limit policy")
    click.echo(
        f"  minimum interval: {policy['min_interval_seconds']}s"
        f" | window: {policy['max_requests']} requests/{policy['window_seconds']}s"
        f" | server cooldown: {policy['server_cooldown_seconds']}s"
    )
    scopes = payload["scopes"]
    if not scopes:
        print_info("No recorded query requests")
        return

    for item in scopes:
        state = (
            f"{item['window_requests']}/{item['max_requests']} in window; "
            f"next allowed in {item['next_allowed_in_seconds']}s"
        )
        if item["last_error"]:
            state += f"; last error: {item['last_error']}"
        click.echo(f"  {item['scope']}: {state}")
