"""Commands backed by the official Zhihu Open Platform CLI."""

from __future__ import annotations

import click

from ..display import print_error, print_info
from ..official import OfficialCliError, run_official
from ..rate_limit import RateLimitError, RateLimitStateError, current_rate_scope


def _scope_prompt() -> None:
    click.echo(
        "Backend: Official API (Access Secret) · public search, own user data, "
        "knowledge bases, and quota; no web-session publishing",
        err=True,
    )


def _rate_scope(official_args: tuple[str, ...]) -> str | None:
    """Rate-limit official search commands while leaving auth/help local."""
    if len(official_args) >= 2 and official_args[0] == "search":
        if official_args[1] == "zhihu":
            if not _valid_search_count(official_args[2:], maximum=10):
                return None
            return current_rate_scope("api", "zhihu_search")
        if official_args[1] == "global":
            if not _valid_search_count(official_args[2:], maximum=20):
                return None
            return current_rate_scope("api", "global_search")
    return None


def _valid_search_count(args: tuple[str, ...], *, maximum: int) -> bool:
    """Avoid reserving a slot for an Official API argument validation failure."""
    count: int | None = None
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--count":
            if index + 1 >= len(args):
                return False
            raw_count = args[index + 1]
            index += 1
        elif argument.startswith("--count="):
            raw_count = argument.partition("=")[2]
        else:
            index += 1
            continue
        try:
            count = int(raw_count)
        except ValueError:
            return False
        index += 1
    return count is None or 1 <= count <= maximum


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
        kwargs = {
            "timeout": float((ctx.find_root().obj or {}).get("official_timeout", 60)),
        }
        rate_scope = _rate_scope(official_args)
        if rate_scope:
            kwargs["rate_scope"] = rate_scope
        result = run_official(list(official_args), **kwargs)
    except RateLimitError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(exc.exit_code) from exc
    except RateLimitStateError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc
    except OfficialCliError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc

    if result.stdout:
        click.echo(result.stdout, nl=False)
    if result.stderr:
        click.echo(result.stderr, nl=False, err=True)
    raise click.exceptions.Exit(result.returncode)
