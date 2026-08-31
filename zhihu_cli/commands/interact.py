"""Interaction commands: vote, follow-question, ask, pin, collections, notifications."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import click

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    make_table,
    print_error,
    print_hint,
    print_info,
    print_success,
    print_warning,
    strip_html,
    truncate,
)


@contextmanager
def _get_client():
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)
    with ZhihuClient(cookie_str_to_dict(cookie)) as client:
        yield client


def _require_writable(ctx: click.Context) -> None:
    """Stop a mutating command when the root CLI is read-only."""
    root = ctx.find_root()
    if (root.obj or {}).get("readonly"):
        print_error(
            "Read-only mode is enabled; this command would modify Zhihu data."
        )
        raise click.exceptions.Exit(2)


def _dry_run_requested(
    dry_run: bool, execute: bool, action: str,
) -> bool:
    """Validate write mode and print a side-effect-free preview."""
    if dry_run and execute:
        raise click.UsageError("--dry-run and --execute cannot be used together")
    if dry_run:
        print_info(f"Dry-run: would {action}; no request or upload was sent")
        return True
    return False


def _preview_until_execute(
    dry_run: bool, execute: bool, action: str,
) -> bool:
    """Keep newly added write commands preview-only until --execute is given."""
    if dry_run and execute:
        raise click.UsageError("--dry-run and --execute cannot be used together")
    if dry_run or not execute:
        print_info(
            f"Dry-run: would {action}; add [bold]--execute[/bold] to send it"
        )
        return True
    return False


@click.command()
@click.argument("answer_id", type=int)
@click.option("--up", "action", flag_value="up", default=True, help="Upvote (default)")
@click.option("--neutral", "action", flag_value="neutral", help="Cancel vote")
@click.option("--dry-run", is_flag=True, help="Preview without sending a vote")
@click.option("--execute", is_flag=True, help="Execute the vote explicitly")
@click.pass_context
def vote(ctx: click.Context, answer_id: int, action: str, dry_run: bool, execute: bool):
    """Vote on an answer."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"vote on answer {answer_id}"):
        return
    with _get_client() as client:
        try:
            if action == "up":
                client.vote_up(answer_id)
                print_success(f"Upvoted answer [bold]{answer_id}[/bold]")
            else:
                client.vote_neutral(answer_id)
                print_success(f"Cancelled vote on answer [bold]{answer_id}[/bold]")
        except Exception as e:
            print_error(f"Vote failed: {e}")
            sys.exit(1)


@click.command("follow-question")
@click.argument("question_id", type=int)
@click.option("--unfollow", is_flag=True, help="Unfollow instead")
@click.option("--dry-run", is_flag=True, help="Preview without changing follows")
@click.option("--execute", is_flag=True, help="Execute the follow change explicitly")
@click.pass_context
def follow_question(
    ctx: click.Context, question_id: int, unfollow: bool,
    dry_run: bool, execute: bool,
):
    """Follow or unfollow a question."""
    _require_writable(ctx)
    verb = "unfollow" if unfollow else "follow"
    if _dry_run_requested(dry_run, execute, f"{verb} question {question_id}"):
        return
    with _get_client() as client:
        try:
            if unfollow:
                client.unfollow_question(question_id)
                print_success(f"Unfollowed question [bold]{question_id}[/bold]")
            else:
                client.follow_question(question_id)
                print_success(f"Followed question [bold]{question_id}[/bold]")
        except Exception as e:
            print_error(f"Operation failed: {e}")
            sys.exit(1)


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def collections(limit: int, as_json: bool):
    """List your collections (收藏夹)."""
    with _get_client() as client:
        try:
            results = client.get_collections(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch collections: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No collections found")
            return

        table = make_table(" My Collections ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", ratio=1)
        table.add_column("Items", width=10, justify="right")

        for i, col in enumerate(data, 1):
            title = col.get("title", "—")
            count = format_count(col.get("item_count", col.get("answer_count", 0)))
            table.add_row(str(i), title, count)

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.argument("collection_id", type=str)
@click.option("-l", "--limit", default=20, help="Number of items", show_default=True)
@click.option("--offset", default=0, help="Pagination offset", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def collection(collection_id: str, limit: int, offset: int, as_json: bool):
    """List items in a collection (收藏夹内容)."""
    with _get_client() as client:
        try:
            results = client.get_collection_items(
                collection_id, offset=offset, limit=limit,
            )
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch collection: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("Collection is empty")
            return

        table = make_table(f" Collection {collection_id} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Type", width=10)
        table.add_column("ID", width=20)
        table.add_column("Title / Excerpt", ratio=1)

        for index, item in enumerate(data, 1):
            question = item.get("question") or {}
            title = (
                item.get("title")
                or question.get("title")
                or item.get("excerpt_title")
                or item.get("excerpt")
                or "（无标题）"
            )
            table.add_row(
                str(index),
                str(item.get("type") or "—"),
                str(item.get("id") or "—"),
                truncate(strip_html(title), 100),
            )

        console.print()
        console.print(table)
        console.print()


def _format_notification_line(n: dict) -> str:
    """Format a single notification (v2/recent) for display."""
    content = n.get("content") or {}
    actors = content.get("actors") or []
    verb = (content.get("verb") or "").strip()
    target = content.get("target") or {}
    target_text = strip_html(target.get("text", ""))
    names = ", ".join(a.get("name", "") for a in actors if a.get("name"))
    if names and verb:
        line = f"{names} {verb}"
    elif target_text:
        line = target_text
    else:
        line = verb or "—"
    if target_text and line != target_text:
        line = f"{line} · {target_text}"
    return line.strip() or "—"


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--offset", default=0, help="Pagination offset (from paging.next)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def notifications(limit: int, offset: int, as_json: bool):
    """Show recent notifications (v2/recent)."""
    with _get_client() as client:
        try:
            results = client.get_notifications(limit=limit, offset=offset)
            data = results.get("data", [])
            paging = results.get("paging", {})
        except Exception as e:
            print_error(f"Failed to fetch notifications: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No notifications")
            return

        table = make_table(" Notifications ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Read", width=5)
        table.add_column("Content", ratio=1)

        for i, n in enumerate(data, 1):
            is_read = "✓" if n.get("is_read") else "·"
            line = _format_notification_line(n)
            table.add_row(str(i), is_read, line)

        console.print()
        console.print(table)
        next_url = paging.get("next") or ""
        if not paging.get("is_end") and next_url and "offset=" in next_url:
            try:
                qs = parse_qs(urlparse(next_url).query)
                next_offset = (qs.get("offset") or [None])[0]
                if next_offset:
                    print_hint(f"Next page: zhihu notifications --offset {next_offset} -l {limit}")
            except Exception:
                pass
        console.print()


@click.command()
@click.argument("title")
@click.option("-d", "--detail", default="", help="Question description")
@click.option("-t", "--topic", "topics", multiple=True, help="Topic ID (repeatable)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
@click.option("--dry-run", is_flag=True, help="Preview without publishing")
@click.option("--execute", is_flag=True, help="Publish explicitly")
@click.pass_context
def ask(
    ctx: click.Context, title: str, detail: str,
    topics: tuple[str, ...], images: tuple[str, ...],
    dry_run: bool, execute: bool,
):
    """Post a new question (发布提问)."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"post question {title!r}"):
        return
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="question")
                    image_infos.append(info)

            result = client.create_question(
                title=title.strip(),
                detail=detail,
                topic_ids=list(topics) if topics else None,
                image_infos=image_infos,
            )
            qid = result.get("id", "")
            if qid:
                print_success(
                    f"Question created!  ID: [bold]{qid}[/bold]\n"
                    f"  https://www.zhihu.com/question/{qid}"
                )
            else:
                print_warning("Question may have been created but no ID returned")
        except Exception as e:
            print_error(f"Failed to create question: {e}")
            sys.exit(1)


@click.command("answer-post")
@click.argument("question_id", type=int)
@click.option("--content", default="", help="Answer content")
@click.option("--file", "content_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--anonymous", is_flag=True, help="Post anonymously")
@click.option("--dry-run", is_flag=True, help="Preview without posting")
@click.option("--execute", is_flag=True, help="Post explicitly")
@click.pass_context
def answer_post(
    ctx: click.Context,
    question_id: int,
    content: str,
    content_file: Path | None,
    anonymous: bool,
    dry_run: bool,
    execute: bool,
):
    """Post an answer; preview-only unless --execute is provided."""
    _require_writable(ctx)
    if content and content_file:
        raise click.UsageError("Use either --content or --file, not both")
    if content_file:
        try:
            content = content_file.read_text(encoding="utf-8")
        except OSError as e:
            raise click.ClickException(f"Cannot read answer file: {e}") from e
    if not content.strip():
        raise click.UsageError("Answer content cannot be empty")
    if _preview_until_execute(
        dry_run, execute, f"post an answer to question {question_id}",
    ):
        return

    with _get_client() as client:
        try:
            result = client.create_answer(
                str(question_id), content.strip(), is_anonymous=anonymous,
            )
            answer_id = result.get("id") or (result.get("data") or {}).get("id", "")
            print_success(f"Answer posted! ID: [bold]{answer_id or '—'}[/bold]")
        except Exception as e:
            print_error(f"Failed to post answer: {e}")
            sys.exit(1)


@click.command()
@click.argument("target_type", type=click.Choice(["answer", "article", "pin"]))
@click.argument("target_id", type=str)
@click.argument("content")
@click.option("--reply-to", default=None, help="Reply to a comment ID")
@click.option("--dry-run", is_flag=True, help="Preview without posting")
@click.option("--execute", is_flag=True, help="Post explicitly")
@click.pass_context
def comment(
    ctx: click.Context,
    target_type: str,
    target_id: str,
    content: str,
    reply_to: str | None,
    dry_run: bool,
    execute: bool,
):
    """Post a comment; preview-only unless --execute is provided."""
    _require_writable(ctx)
    if not content.strip():
        raise click.UsageError("Comment content cannot be empty")
    if _preview_until_execute(
        dry_run, execute, f"comment on {target_type} {target_id}",
    ):
        return

    with _get_client() as client:
        try:
            result = client.create_comment(
                target_type, target_id, content.strip(), reply_to=reply_to,
            )
            comment_id = result.get("id") or (result.get("data") or {}).get("id", "")
            print_success(f"Comment posted! ID: [bold]{comment_id or '—'}[/bold]")
        except Exception as e:
            print_error(f"Failed to post comment: {e}")
            sys.exit(1)


@click.command()
@click.argument("title")
@click.option("-c", "--content", default="", help="Pin body content (optional)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
@click.option("--dry-run", is_flag=True, help="Preview without publishing")
@click.option("--execute", is_flag=True, help="Publish explicitly")
@click.pass_context
def pin(
    ctx: click.Context, title: str, content: str,
    images: tuple[str, ...], dry_run: bool, execute: bool,
):
    """Write a new pin / thought (发布想法). Title and content, payload similar to question."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"publish pin {title!r}"):
        return
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="pin")
                    image_infos.append(info)

            result = client.create_pin(
                title=title.strip(),
                content=content.strip(),
                image_infos=image_infos,
            )
            pid = result.get("id", "")
            if pid:
                print_success(
                    f"Pin published!  ID: [bold]{pid}[/bold]\n"
                    f"  https://www.zhihu.com/pin/{pid}"
                )
            else:
                print_warning("Pin may have been created but no ID returned")
        except Exception as e:
            print_error(f"Failed to create pin: {e}")
            sys.exit(1)


@click.command()
@click.argument("title")
@click.argument("content")
@click.option("-t", "--topic", "topics", multiple=True, help="Topic ID (repeatable)")
@click.option("-i", "--image", "images", multiple=True, help="Image file path (repeatable)")
@click.option("--dry-run", is_flag=True, help="Preview without publishing")
@click.option("--execute", is_flag=True, help="Publish explicitly")
@click.pass_context
def article(
    ctx: click.Context, title: str, content: str,
    topics: tuple[str, ...], images: tuple[str, ...],
    dry_run: bool, execute: bool,
):
    """Publish a new article (发布文章)."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"publish article {title!r}"):
        return
    if not title.strip():
        print_error("Title cannot be empty")
        sys.exit(1)
    if not content.strip():
        print_error("Content cannot be empty")
        sys.exit(1)

    with _get_client() as client:
        try:
            body = f"<p>{content.strip()}</p>"
            image_infos = None
            if images:
                image_infos = []
                for img_path in images:
                    print_info(f"Uploading image: {img_path}")
                    info = client.upload_image(img_path, source="article")
                    image_infos.append(info)

            result = client.create_article(
                title=title.strip(),
                content=body,
                image_infos=image_infos,
                topic_ids=list(topics) if topics else None,
            )
            aid = result.get("id", "")
            if aid:
                print_success(
                    f"Article published!  ID: [bold]{aid}[/bold]\n"
                    f"  https://zhuanlan.zhihu.com/p/{aid}"
                )
            else:
                print_warning("Article may have been published but no ID returned")
        except Exception as e:
            print_error(f"Failed to publish article: {e}")
            sys.exit(1)


@click.command("delete-question")
@click.argument("question_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--execute", is_flag=True, help="Delete explicitly")
@click.pass_context
def delete_question(
    ctx: click.Context, question_id: str, skip_confirm: bool,
    dry_run: bool, execute: bool,
):
    """Delete your own question (删除自己发布的提问)."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"delete question {question_id}"):
        return
    if not skip_confirm:
        click.confirm(f"Delete question {question_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_question(question_id)
            if ok:
                print_success(f"Question [bold]{question_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)


@click.command("delete-pin")
@click.argument("pin_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--execute", is_flag=True, help="Delete explicitly")
@click.pass_context
def delete_pin(
    ctx: click.Context, pin_id: str, skip_confirm: bool,
    dry_run: bool, execute: bool,
):
    """Delete your own pin / thought (删除自己发布的想法)."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"delete pin {pin_id}"):
        return
    if not skip_confirm:
        click.confirm(f"Delete pin {pin_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_pin(pin_id)
            if ok:
                print_success(f"Pin [bold]{pin_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)


@click.command("delete-article")
@click.argument("article_id", type=str)
@click.option("-y", "--yes", "skip_confirm", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--execute", is_flag=True, help="Delete explicitly")
@click.pass_context
def delete_article_cmd(
    ctx: click.Context, article_id: str, skip_confirm: bool,
    dry_run: bool, execute: bool,
):
    """Delete your own article (删除自己发布的文章)."""
    _require_writable(ctx)
    if _dry_run_requested(dry_run, execute, f"delete article {article_id}"):
        return
    if not skip_confirm:
        click.confirm(f"Delete article {article_id}? This cannot be undone.", abort=True)
    with _get_client() as client:
        try:
            ok = client.delete_article(article_id)
            if ok:
                print_success(f"Article [bold]{article_id}[/bold] deleted")
            else:
                print_error("Delete request was not accepted by the server")
                sys.exit(1)
        except Exception as e:
            print_error(f"Delete failed: {e}")
            sys.exit(1)
