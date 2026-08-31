"""Authentication commands: login, logout, status, whoami."""

from __future__ import annotations

import json
import sys

import click
from click.core import ParameterSource

from ..accounts import AccountError, get_account_store
from ..auth import (
    clear_cookies,
    cookie_str_to_dict,
    get_cookie_string,
    get_saved_cookie_string,
    qrcode_login,
    save_cookies,
)
from ..config import REQUIRED_COOKIES
from ..display import (
    console,
    format_count,
    make_kv_table,
    print_error,
    print_hint,
    print_info,
    print_success,
    print_warning,
    strip_html,
)
from ..official import OfficialCliError, run_official


def _verify_cookies(cookie_dict: dict) -> bool | None:
    """Validate cookies by fetching user info.

    Returns True/False/None for valid/invalid/unknown.
    """
    from ..client import ZhihuClient

    try:
        with ZhihuClient(cookie_dict) as client:
            info = client.get_self_info()
    except Exception:
        return None

    if not isinstance(info, dict) or not info:
        return None

    name = info.get("name", "")
    uid = info.get("id", "")
    if name and name != "知乎用户":
        return True
    if uid:
        return True
    return False


@click.command()
@click.option("--qrcode", is_flag=True, help="Use QR code to login")
@click.option("--cookie", "cookie_str", default=None, help="Provide cookie string directly")
@click.option("--api", "api_login", is_flag=True, help="Use the official Access Secret backend")
@click.option("--account", "account_name", default=None, help="Save login under this account name")
@click.pass_context
def login(
    ctx: click.Context,
    qrcode: bool,
    cookie_str: str | None,
    api_login: bool,
    account_name: str | None,
):
    """Authenticate with Zhihu.

    \b
    Methods:
      --qrcode   Scan QR code with Zhihu app (recommended)
      --cookie   Paste cookie string (must contain z_c0, _xsrf, d_c0)
      --api      Configure the official Open Platform Access Secret
    """
    cookie_provided = (
        ctx.get_parameter_source("cookie_str") == ParameterSource.COMMANDLINE
    )
    account_name = account_name or (ctx.find_root().obj or {}).get("account")

    if api_login:
        if qrcode or cookie_provided:
            raise click.UsageError("--api cannot be combined with --qrcode or --cookie")
        click.echo(
            "Backend: Official API (Access Secret) · API-only scope; input is hidden",
            err=True,
        )
        secret = click.prompt("Access Secret", hide_input=True, confirmation_prompt=False)
        try:
            if account_name:
                result = run_official(
                    ["auth", "status", "--verify"],
                    access_secret=secret,
                    timeout=60,
                )
            else:
                result = run_official(
                    ["auth", "set", "--secret-stdin"],
                    input_text=secret,
                    timeout=60,
                )
        except OfficialCliError as exc:
            print_error(str(exc))
            raise click.exceptions.Exit(1) from exc
        if result.returncode != 0:
            if result.stderr:
                click.echo(result.stderr, nl=False, err=True)
            print_error("Official API login failed; the Access Secret was not saved by this CLI.")
            raise click.exceptions.Exit(1)
        if account_name:
            try:
                get_account_store().save_api(account_name, secret)
            except AccountError as exc:
                print_error(str(exc))
                raise click.exceptions.Exit(1) from exc
            print_success(f"Official API account saved securely: {account_name}")
        else:
            print_success("Official API login successful; Access Secret saved by the official CLI")
        return

    if cookie_provided:
        parsed = cookie_str_to_dict(cookie_str or "")
        if not REQUIRED_COOKIES.issubset(parsed.keys()):
            print_error(
                "Invalid cookie — must contain [bold]z_c0[/bold], "
                "[bold]_xsrf[/bold], [bold]d_c0[/bold]"
            )
            sys.exit(1)
        save_cookies(
            "; ".join(f"{k}={v}" for k, v in parsed.items()),
            account_name=account_name,
        )
        print_success(f"Cookie saved for account {account_name or 'default'}")
        return

    if not qrcode:
        cookie = get_cookie_string(account_name)
        if cookie:
            cookie_dict = cookie_str_to_dict(cookie)
            verify_result = _verify_cookies(cookie_dict)
            if verify_result is True:
                print_success("Already authenticated (saved cookie)")
                return
            elif verify_result is False:
                print_warning("Saved cookie expired or invalid")
                clear_cookies(account_name=account_name)
            else:
                print_warning("Cannot verify cookie — keeping existing session")
                return

    # QR code login
    print_info("Launching QR code login…")
    try:
        cookie = qrcode_login()
        save_cookies(cookie, account_name=account_name)
        cookie_dict = cookie_str_to_dict(cookie)
        verify_result = _verify_cookies(cookie_dict)
        if verify_result is False:
            clear_cookies()
            print_error("Login completed but session is invalid — please retry")
            sys.exit(1)
        print_success("Login successful — cookie saved")
    except Exception as e:
        print_error(f"Login failed: {e}")
        sys.exit(1)


@click.command()
def logout():
    """Clear saved credentials."""
    removed = clear_cookies()
    if removed:
        print_success(f"Logged out — removed: {', '.join(removed)}")
    else:
        print_warning("No saved credentials to clear")


@click.command()
def status():
    """Check authentication status (offline)."""
    cookie = get_saved_cookie_string()
    if not cookie:
        print_error("Not authenticated")
        print_hint("Run [bold]zhihu login --qrcode[/bold] or [bold]zhihu login --cookie[/bold]")
        sys.exit(1)

    print_success("Authenticated [dim](saved cookie)[/dim]")
    print_hint("Run [bold]zhihu whoami[/bold] to view profile")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def whoami(as_json: bool):
    """Show current user profile."""
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)

    try:
        with ZhihuClient(cookie_str_to_dict(cookie)) as client:
            info = client.get_self_info()

            if as_json:
                click.echo(json.dumps(info, indent=2, ensure_ascii=False))
                return

            name = info.get("name", "Unknown")
            headline = info.get("headline", "")
            url_token = info.get("url_token", "")
            gender = info.get("gender", -1)
            description = strip_html(info.get("description", ""))

            table = make_kv_table(f"  {name}  ")

            if url_token:
                table.add_row("ID", f"@{url_token}")
            if headline:
                table.add_row("Headline", headline)
            if description:
                table.add_row("Bio", description[:80])

            gender_label = {0: "Male", 1: "Female", -1: "—"}.get(gender, str(gender))
            table.add_row("Gender", gender_label)

            table.add_row("Answers", format_count(info.get("answer_count", 0)))
            table.add_row("Articles", format_count(info.get("articles_count", 0)))
            table.add_row("Followers", format_count(info.get("follower_count", 0)))
            table.add_row("Following", format_count(info.get("following_count", 0)))
            table.add_row("Upvotes", format_count(info.get("voteup_count", 0)))
            table.add_row("Thanks", format_count(info.get("thanked_count", 0)))

            console.print()
            console.print(table)
            console.print()

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Failed to fetch profile: {e}")
        sys.exit(1)
