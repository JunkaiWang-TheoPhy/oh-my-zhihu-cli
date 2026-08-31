"""CLI entry point for zhihu-cli."""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands.accounts import account
from .commands.auth import login, logout, status, whoami
from .commands.config import config
from .commands.content import answer, answers, drafts, feed, feeds, hot, question, search, topic
from .commands.guidance import guidance
from .commands.interact import (
    article,
    ask,
    collections,
    delete_article_cmd,
    delete_pin,
    delete_question,
    follow_question,
    notifications,
    pin,
    vote,
)
from .commands.official import api
from .commands.user import followers, following, user, user_answers, user_articles
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
@click.option(
    "--readonly",
    "--read-only",
    is_flag=True,
    help="Block commands that write, interact, or delete on Zhihu",
)
@click.option("--api", "force_api", is_flag=True, help="Use the Official API backend")
@click.option("--session", "force_session", is_flag=True, help="Use the Web Session backend")
@click.option(
    "--account", "account_name", default=None, help="Use a named account for this command"
)
@click.option(
    "--classic",
    is_flag=True,
    help="Use one-shot CLI output instead of the full-screen console",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    readonly: bool,
    force_api: bool,
    force_session: bool,
    account_name: str | None,
    classic: bool,
):
    """zhihu-cli — Zhihu from your terminal."""
    if force_api and force_session:
        raise click.UsageError("--api and --session cannot be used together")
    _setup_logging(verbose)
    ctx.ensure_object(dict)["readonly"] = readonly
    ctx.ensure_object(dict)["account"] = account_name
    ctx.ensure_object(dict)["backend"] = (
        "api" if force_api else "session" if force_session else None
    )
    if ctx.invoked_subcommand is None:
        print_banner()


# Auth
cli.add_command(login)
cli.add_command(logout)
cli.add_command(status)
cli.add_command(whoami)
cli.add_command(api)
cli.add_command(config)
cli.add_command(account)
cli.add_command(account, name="accounts")
cli.add_command(guidance)
cli.add_command(guidance, name="guide")

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
cli.add_command(pin)
cli.add_command(article)
cli.add_command(delete_question)
cli.add_command(delete_pin)
cli.add_command(delete_article_cmd)
cli.add_command(collections)
cli.add_command(notifications)


@click.command(name="zhihu-tui")
@click.option(
    "--readonly",
    "--read-only",
    is_flag=True,
    help="Block commands that write, interact, or delete on Zhihu",
)
@click.option("--api", "force_api", is_flag=True, help="Prefer the Official API backend")
@click.option("--session", "force_session", is_flag=True, help="Prefer the Web Session backend")
@click.option("--account", "account_name", default=None, help="Use a named account")
def tui_command(
    readonly: bool,
    force_api: bool,
    force_session: bool,
    account_name: str | None,
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
    """Console-script entry point for ``zhihu-tui``."""
    tui_command()


if __name__ == "__main__":
    cli()
