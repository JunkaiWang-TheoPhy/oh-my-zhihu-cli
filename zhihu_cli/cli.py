"""CLI entry point for zhihu-cli."""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands.accounts import account
from .commands.auth import login, logout, profiles, status, whoami
from .commands.backup import drafts_backup, drafts_diff
from .commands.config import config
from .commands.content import (
    answer,
    answers,
    article_read,
    drafts,
    feed,
    feeds,
    hot,
    pin_read,
    question,
    search,
    topic,
)
from .commands.guidance import guidance
from .commands.interact import (
    answer_post,
    article,
    ask,
    collection,
    collections,
    comment,
    delete_article_cmd,
    delete_pin,
    delete_question,
    follow_question,
    notifications,
    pin,
    vote,
)
from .commands.official import api
from .commands.rate_limit import rate_limit
from .commands.user import followers, following, user, user_answers, user_articles
from .config import DEFAULT_TIMEOUT, validate_profile
from .console import run_tui
from .display import print_banner


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="zhihu-cli")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
@click.option("--profile", default="default", show_default=True, help="Account profile")
@click.option(
    "--timeout", type=click.FloatRange(min=0.1), default=DEFAULT_TIMEOUT,
    show_default=True, help="HTTP timeout in seconds",
)
@click.option(
    "--retry", type=click.IntRange(min=0, max=5), default=0,
    show_default=True, help="Retries for failed GET requests",
)
@click.option(
    "--readonly", "--read-only", is_flag=True,
    help="Block commands that write, interact, or delete on Zhihu",
)
@click.option(
    "--account", "account_name", default=None, help="Use a named account for this command"
)
@click.option("--api", "force_api", is_flag=True, help="Use the Official API backend")
@click.option("--session", "force_session", is_flag=True, help="Use the Web Session backend")
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    profile: str,
    timeout: float,
    retry: int,
    readonly: bool,
    account_name: str | None,
    force_api: bool,
    force_session: bool,
):
    """zhihu-cli — Zhihu from your terminal."""
    try:
        profile = validate_profile(profile)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--profile") from e
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile
    ctx.obj["timeout"] = timeout
    ctx.obj["official_timeout"] = 60.0
    ctx.obj["retry"] = retry
    ctx.obj["readonly"] = readonly
    ctx.obj["account"] = account_name
    ctx.obj["backend"] = "api" if force_api else "session" if force_session else None
    _setup_logging(verbose)
    if ctx.invoked_subcommand is None:
        print_banner()


# Auth
cli.add_command(login)
cli.add_command(logout)
cli.add_command(status)
cli.add_command(profiles)
cli.add_command(whoami)
cli.add_command(account)
cli.add_command(account, name="accounts")
cli.add_command(api)
cli.add_command(rate_limit)
cli.add_command(guidance)
cli.add_command(guidance, name="guide")
cli.add_command(config)

# Content
cli.add_command(search)
cli.add_command(hot)
cli.add_command(question)
cli.add_command(answers)
cli.add_command(answer)
cli.add_command(feed)
cli.add_command(feeds)
cli.add_command(topic)
cli.add_command(drafts)
cli.add_command(article_read)
cli.add_command(pin_read)
cli.add_command(drafts_backup)
cli.add_command(drafts_diff)

# User
cli.add_command(user)
cli.add_command(user_answers)
cli.add_command(user_articles)
cli.add_command(followers)
cli.add_command(following)

# Interactions
cli.add_command(vote)
cli.add_command(follow_question)
cli.add_command(ask)
cli.add_command(answer_post)
cli.add_command(comment)
cli.add_command(pin)
cli.add_command(article)
cli.add_command(delete_question)
cli.add_command(delete_pin)
cli.add_command(delete_article_cmd)
cli.add_command(collections)
cli.add_command(collection)
cli.add_command(notifications)


@click.command(name="zhihu-tui")
@click.option("--readonly", "--read-only", is_flag=True)
@click.option("--account", "account_name", default=None, help="Use a named account")
@click.option("--api", "force_api", is_flag=True)
@click.option("--session", "force_session", is_flag=True)
def tui_command(
    readonly: bool,
    account_name: str | None,
    force_api: bool,
    force_session: bool,
) -> None:
    """Open the full-screen Zhihu workbench."""
    if force_api and force_session:
        raise click.UsageError("--api and --session cannot be used together")
    run_tui(
        readonly=readonly,
        backend="api" if force_api else "session" if force_session else None,
        account=account_name,
    )


def tui_entry() -> None:
    tui_command()


if __name__ == "__main__":
    cli()
