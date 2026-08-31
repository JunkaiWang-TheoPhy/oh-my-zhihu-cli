"""Named account management commands."""

from __future__ import annotations

import click

from ..accounts import AccountError, get_account_store
from ..display import make_table, print_error, print_success


@click.group()
def account() -> None:
    """List, select, and remove named Zhihu accounts."""


@account.command("list")
@click.option("--backend", type=click.Choice(["session", "api"]), default=None)
def list_accounts(backend: str | None) -> None:
    store = get_account_store()
    entries = store.list(backend)
    table = make_table(" Accounts ")
    table.add_column("Active", width=8)
    table.add_column("Backend", width=10)
    table.add_column("Name", ratio=1)
    for item in entries:
        table.add_row("●" if item.active else "", item.backend, item.name)
    from ..display import console

    console.print(table)


@account.command("current")
def current_account() -> None:
    store = get_account_store()
    click.echo(f"Session: {store.active_name('session') or 'none'}")
    click.echo(f"Official API: {store.active_name('api') or 'default/system'}")


@account.command("use")
@click.argument("name")
@click.option("--backend", type=click.Choice(["session", "api"]), required=True)
def use_account(name: str, backend: str) -> None:
    try:
        get_account_store().use(name, backend)
    except AccountError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc
    print_success(f"Active {backend} account: {name}")


@account.command("remove")
@click.argument("name")
@click.option("--backend", type=click.Choice(["session", "api"]), required=True)
@click.option("--yes", is_flag=True, help="Skip confirmation")
def remove_account(name: str, backend: str, yes: bool) -> None:
    if not yes and not click.confirm(f"Remove {backend} account {name}?"):
        return
    try:
        get_account_store().remove(name, backend)
    except AccountError as exc:
        print_error(str(exc))
        raise click.exceptions.Exit(1) from exc
    print_success(f"Removed {backend} account: {name}")
