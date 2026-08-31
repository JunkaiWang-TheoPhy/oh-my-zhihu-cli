"""Commands backed by the official Zhihu Open Platform CLI."""

from __future__ import annotations

import click

from ..display import print_error, print_info
from ..official import OfficialCliError, run_official


def _scope_prompt() -> None:
    click.echo(
        "Backend: Official API (Access Secret) · public search, own user data, "
        "knowledge bases, and quota; no web-session publishing",
        err=True,
    )


@click.command(
    "api",
    add_help_option=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("official_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def api(ctx: click.Context, official_args: tuple[str, ...]) -> None:
    """Run a command from the official Zhihu Open Platform CLI."""
    if not official_args:
        _scope_prompt()
        print_info("Usage: zhihu api <official zhihu-cli command> [flags]")
        print_info("Try: zhihu api capabilities")
        raise click.exceptions.Exit(2)

    if (ctx.find_root().obj or {}).get("readonly") and official_args[:2] == (
        "knowledge", "upload",
    ):
        print_error("Read-only mode is enabled; official knowledge upload is disabled.")
        raise click.exceptions.Exit(2)

    _scope_prompt()
    try:
        result = run_official(
            list(official_args),
            timeout=float((ctx.find_root().obj or {}).get("timeout", 60)),
        )
    except OfficialCliError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc

    if result.stdout:
        click.echo(result.stdout, nl=False)
    if result.stderr:
        click.echo(result.stderr, nl=False, err=True)
    raise click.exceptions.Exit(result.returncode)
