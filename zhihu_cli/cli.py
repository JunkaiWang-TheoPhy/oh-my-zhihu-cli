"""CLI entry point for zhihu-cli."""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands.auth import login, logout, profiles, status, whoami
from .commands.backup import drafts_backup, drafts_diff
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
from .commands.interact import (
    article,
    ask,
    answer_post,
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
from .commands.user import followers, following, user, user_answers, user_articles
from .config import DEFAULT_TIMEOUT, validate_profile


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
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
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    profile: str,
    timeout: float,
    retry: int,
    readonly: bool,
):
    """zhihu-cli — Zhihu from your terminal."""
    try:
        profile = validate_profile(profile)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--profile") from e
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile
    ctx.obj["timeout"] = timeout
    ctx.obj["retry"] = retry
    ctx.obj["readonly"] = readonly
    _setup_logging(verbose)


# Auth
cli.add_command(login)
cli.add_command(logout)
cli.add_command(status)
cli.add_command(profiles)
cli.add_command(whoami)

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


if __name__ == "__main__":
    cli()
