"""Content browsing commands: search, hot, question, answer, feed, topic, drafts."""

from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import click
from rich.text import Text

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    format_stats_line,
    make_table,
    print_error,
    print_hint,
    print_info,
    print_success,
    strip_html,
    truncate,
)
from ..official import OfficialCliError, run_official
from ..routing import BackendUnavailable, choose_backend, first_run_guidance, load_settings


@contextmanager
def _get_client():
    """Create an authenticated ZhihuClient."""
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)
    with ZhihuClient(cookie_str_to_dict(cookie)) as client:
        yield client


def _draft_title_and_body(item: dict) -> tuple[str, str]:
    """Extract display text from a pin draft's rich-content payload."""
    result = item.get("result") or {}
    parts = result.get("content") or []
    title = ""
    body_parts = []

    for part in parts:
        if not isinstance(part, dict):
            continue
        if not title and isinstance(part.get("title"), str):
            title = strip_html(part["title"])
        for field in ("content", "own_text"):
            value = part.get(field)
            if isinstance(value, str) and value.strip():
                text = strip_html(value)
                if text and text != title and text not in body_parts:
                    body_parts.append(text)
                break

    return title or "（无标题）", " ".join(body_parts)


def _format_draft_time(value) -> str:
    """Format a Zhihu timestamp for terminal output."""
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return "—"


def _article_plain_text(content: str) -> str:
    """Convert article HTML into readable terminal text."""
    if not content:
        return ""
    content = re.sub(
        r"<(?:br\s*/?|/(?:p|div|li|h[1-6]|blockquote))\s*>",
        "\n",
        content,
        flags=re.IGNORECASE,
    )
    return strip_html(content)


def _merge_paged_result(last_result: dict, items: list, total) -> dict:
    """Build a JSON response containing all fetched pages."""
    output = dict(last_result)
    output["data"] = items
    output["paging"] = dict(output.get("paging") or {})
    output["paging"].update({
        "is_start": True,
        "is_end": True,
        "next": None,
        "totals": total if total is not None else len(items),
    })
    return output


def _fetch_draft_pages(fetch_page, limit: int, fetch_all: bool):
    """Fetch one page or all pages from a draft list endpoint."""
    offset = 0
    all_items = []
    last_result = {}
    total = None

    while True:
        result = fetch_page(offset=offset, limit=limit)
        page = result.get("data") or []
        if not isinstance(page, list):
            raise ValueError("Draft list returned invalid data")
        all_items.extend(page)
        last_result = result

        paging = result.get("paging") or {}
        total = paging.get("totals", total)
        if not fetch_all or paging.get("is_end", True) or not page:
            break

        next_offset = offset + len(page)
        if next_offset <= offset:
            break
        offset = next_offset

    return all_items, last_result, total


def _draft_search_text(draft_type: str, item: dict) -> str:
    """Return searchable text for a draft list item."""
    if draft_type == "article":
        return " ".join(str(item.get(key) or "") for key in ("title", "summary"))
    if draft_type == "answer":
        question = item.get("question") or {}
        return " ".join(str(value or "") for value in (
            question.get("title"), item.get("excerpt"), item.get("content"),
        ))
    if draft_type == "video":
        return " ".join(str(item.get(key) or "") for key in ("title", "description"))
    title, body = _draft_title_and_body(item)
    return f"{title} {body}"


def _draft_title_and_content(client, draft_type: str, item: dict) -> tuple[str, str]:
    """Return a draft title and readable body for Markdown export."""
    if draft_type == "article":
        detail = client.get_article_draft(str(item.get("id")))
        return (
            strip_html(detail.get("title") or "（无标题）"),
            _article_plain_text(detail.get("content") or ""),
        )
    if draft_type == "answer":
        question = item.get("question") or {}
        title = strip_html(question.get("title") or "（无题目）")
        content = item.get("content") or item.get("editable_content") or item.get("excerpt") or ""
        if isinstance(content, dict):
            content = content.get("content") or content.get("text") or ""
        return title, _article_plain_text(str(content))
    if draft_type == "video":
        return (
            strip_html(item.get("title") or "（无标题）"),
            strip_html(item.get("description") or ""),
        )
    return _draft_title_and_body(item)


def _write_markdown_export(
    client,
    draft_type: str,
    items: list[dict],
    output_path: Path,
) -> None:
    """Write selected drafts to a Markdown file."""
    blocks = ["# 知乎草稿导出", ""]
    for index, item in enumerate(items, 1):
        title, content = _draft_title_and_content(client, draft_type, item)
        draft_id = item.get("id") or item.get("content_id") or "—"
        updated = item.get("updated") or item.get("updated_time") or item.get("updated_at")
        if draft_type == "idea":
            updated = item.get("updated_at") or (item.get("result") or {}).get("updated_at")
        blocks.extend([
            f"## {index}. {title}",
            "",
            f"- 类型：{draft_type}",
            f"- ID：{draft_id}",
            f"- 更新时间：{_format_draft_time(updated)}",
            "",
            content or "（暂无正文）",
            "",
        ])
    output_path.expanduser().resolve().write_text(
        "\n".join(blocks), encoding="utf-8",
    )


@click.command()
@click.option(
    "-l", "--limit", default=20, type=click.IntRange(1, 20),
    help="Number of drafts per page", show_default=True,
)
@click.option(
    "-t", "--type", "draft_type", default="article",
    type=click.Choice(["article", "idea", "answer", "video"]), show_default=True,
    help="Draft type to list",
)
@click.option("--all", "fetch_all", is_flag=True, help="Fetch all pages")
@click.option(
    "--search", "search_term", default="",
    help="Filter this page; combine with --all to search every page",
)
@click.option(
    "--id", "draft_id", type=click.IntRange(min=1),
    help="Read one article draft in full",
)
@click.option(
    "--export-markdown", "export_markdown", type=click.Path(dir_okay=False, path_type=Path),
    help="Export the selected drafts to a Markdown file",
)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def drafts(
    limit: int,
    draft_type: str,
    fetch_all: bool,
    search_term: str,
    draft_id: int | None,
    export_markdown: Path | None,
    as_json: bool,
):
    """List, search, read, or export article and other drafts (read-only)."""
    with _get_client() as client:
        try:
            if as_json and export_markdown:
                raise ValueError("--json and --export-markdown cannot be used together")
            if draft_id is not None:
                if draft_type != "article":
                    raise ValueError("--id is only supported for article drafts")
                detail = client.get_article_draft(str(draft_id))
                if export_markdown:
                    _write_markdown_export(
                        client,
                        draft_type,
                        [{"id": draft_id, **detail}],
                        export_markdown,
                    )
                    print_success(f"Exported draft to {export_markdown}")
                    return
                if as_json:
                    click.echo(json.dumps(detail, indent=2, ensure_ascii=False))
                    return

                title = strip_html(detail.get("title") or "（无标题）")
                updated = _format_draft_time(detail.get("updated"))
                content = _article_plain_text(detail.get("content") or "")
                console.print()
                console.print(Text(title, style="bold cyan"))
                console.print(f"[dim]ID: {draft_id}  Updated: {updated}[/dim]")
                console.print()
                console.print(Text(content or "（无正文）"))
                console.print()
                return

            fetchers = {
                "article": client.get_article_drafts,
                "idea": client.get_drafts,
                "answer": client.get_answer_drafts,
                "video": client.get_video_drafts,
            }
            fetch_page = fetchers[draft_type]
            all_items, last_result, total = _fetch_draft_pages(
                fetch_page, limit, fetch_all,
            )
            if search_term:
                needle = search_term.casefold()
                all_items = [
                    item for item in all_items
                    if needle in _draft_search_text(draft_type, item).casefold()
                ]
                last_result = dict(last_result)
                last_result["data"] = all_items
                last_result["paging"] = dict(last_result.get("paging") or {})
                last_result["paging"]["filtered_count"] = len(all_items)
                if fetch_all:
                    total = len(all_items)
                    last_result["paging"].update({
                        "is_start": True,
                        "is_end": True,
                        "next": None,
                        "totals": total,
                    })
        except Exception as e:
            print_error(f"Failed to fetch drafts: {e}")
            sys.exit(1)

        if export_markdown:
            try:
                _write_markdown_export(
                    client, draft_type, all_items, export_markdown,
                )
            except Exception as e:
                print_error(f"Failed to export drafts: {e}")
                sys.exit(1)
            print_success(
                f"Exported {len(all_items)} {draft_type} drafts to {export_markdown}"
            )
            return

        if as_json:
            output = (
                _merge_paged_result(last_result, all_items, total)
                if fetch_all
                else last_result
            )
            click.echo(json.dumps(output, indent=2, ensure_ascii=False))
            return

        if not all_items:
            print_info(f"No {draft_type} drafts")
            return

        if draft_type == "article":
            table = make_table(
                f" Article Drafts ({total if total is not None else len(all_items)}) "
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", width=21)
            table.add_column("Updated", width=16)
            table.add_column("Words", width=8, justify="right")
            table.add_column("Title", ratio=1)

            for index, item in enumerate(all_items, 1):
                title = strip_html(item.get("title") or "（无标题）")
                table.add_row(
                    str(index),
                    Text(str(item.get("id") or "—")),
                    _format_draft_time(item.get("updated")),
                    str(item.get("content_words") or 0),
                    Text(truncate(title, 70)),
                )
        elif draft_type == "idea":
            table = make_table(
                f" Idea Drafts ({total if total is not None else len(all_items)}) "
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", width=20)
            table.add_column("Updated", width=16)
            table.add_column("Draft", ratio=1)

            for index, item in enumerate(all_items, 1):
                result = item.get("result") or {}
                draft_id = item.get("content_id") or result.get("id") or "—"
                updated_at = item.get("updated_at") or result.get("updated_at")
                title, body = _draft_title_and_body(item)
                summary = title if not body else f"{title}：{body}"
                table.add_row(
                    str(index),
                    str(draft_id),
                    _format_draft_time(updated_at),
                    Text(truncate(summary, 100)),
                )
        elif draft_type == "answer":
            table = make_table(
                f" Answer Drafts ({total if total is not None else len(all_items)}) "
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Updated", width=16)
            table.add_column("Words", width=8, justify="right")
            table.add_column("Question", ratio=1)

            for index, item in enumerate(all_items, 1):
                question = item.get("question") or {}
                question_title = strip_html(
                    question.get("title") or item.get("excerpt") or "（无题目）"
                )
                table.add_row(
                    str(index),
                    _format_draft_time(item.get("updated_time")),
                    str(item.get("content_words") or 0),
                    Text(truncate(question_title, 100)),
                )
        else:
            table = make_table(
                f" Video Drafts ({total if total is not None else len(all_items)}) "
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", width=20)
            table.add_column("Updated", width=16)
            table.add_column("State", width=12)
            table.add_column("Title", ratio=1)

            for index, item in enumerate(all_items, 1):
                state = item.get("zvideo_state") or item.get("type") or "—"
                table.add_row(
                    str(index),
                    Text(str(item.get("id") or "—")),
                    _format_draft_time(item.get("updated_at")),
                    str(state),
                    Text(truncate(strip_html(item.get("title") or "（无标题）"), 70)),
                )

        console.print()
        console.print(table)
        console.print()

        if draft_type == "article":
            print_hint("Use [bold]zhihu drafts --id <ID>[/bold] to read an article in full")

        paging = last_result.get("paging") or {}
        if search_term and not fetch_all and not paging.get("is_end", True):
            print_hint(
                "Search covered the current page; use [bold]--all[/bold] "
                "to search every draft"
            )
        if not fetch_all and not paging.get("is_end", True):
            shown_total = total if total is not None else "更多"
            print_hint(
                f"Showing {len(all_items)} of {shown_total} drafts; "
                "use [bold]zhihu drafts --all[/bold] to fetch all"
            )


@click.command("article-read")
@click.argument("article_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def article_read(article_id: str, as_json: bool):
    """Read a published article by ID."""
    with _get_client() as client:
        try:
            article = client.get_article(article_id)
        except Exception as e:
            print_error(f"Failed to fetch article: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(article, indent=2, ensure_ascii=False))
            return

        title = strip_html(article.get("title") or "（无标题）")
        content = _article_plain_text(article.get("content") or "")
        console.print()
        console.print(Text(title, style="bold cyan"))
        console.print(f"[dim]ID: {article_id}[/dim]")
        console.print()
        console.print(Text(content or "（无正文）"))
        console.print()


@click.command("pin-read")
@click.argument("pin_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def pin_read(pin_id: str, as_json: bool):
    """Read a published idea/pin by ID."""
    with _get_client() as client:
        try:
            pin = client.get_pin(pin_id)
        except Exception as e:
            print_error(f"Failed to fetch pin: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(pin, indent=2, ensure_ascii=False))
            return

        title = strip_html(pin.get("excerpt_title") or "（无标题）")
        content = _article_plain_text(
            pin.get("content_html") or pin.get("content") or ""
        )
        console.print()
        console.print(Text(title, style="bold cyan"))
        console.print(f"[dim]ID: {pin_id}[/dim]")
        console.print()
        console.print(Text(content or "（无正文）"))
        console.print()


@click.command()
@click.argument("query")
@click.option("-t", "--type", "search_type", default="general",
              type=click.Choice(["general", "people", "topic"]),
              help="Search scope")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("-a", "--answers", default=3, help="Answers per question (0=hide)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--session", "force_session", is_flag=True)
@click.option("--api", "force_api", is_flag=True)
@click.pass_context
def search(
    ctx: click.Context, query: str, search_type: str, limit: int, answers: int,
    as_json: bool, force_session: bool, force_api: bool,
):
    """Search Zhihu content."""
    try:
        requested = (
            "session" if force_session else "api" if force_api
            else (ctx.find_root().obj or {}).get("backend")
        )
        backend = choose_backend(requested, load_settings())
    except BackendUnavailable as exc:
        print_error(str(exc))
        click.echo(first_run_guidance(load_settings()["language"]), err=True)
        raise click.exceptions.Exit(1) from exc
    if backend.value == "api":
        if search_type != "general":
            print_error("Official API search supports Zhihu/general search only")
            raise click.exceptions.Exit(2)
        try:
            result = run_official(
                ["search", "zhihu", "--query", query, "--count", str(limit)],
                timeout=60,
            )
        except OfficialCliError as exc:
            print_error(str(exc))
            raise click.exceptions.Exit(1) from exc
        if result.stdout:
            click.echo(result.stdout, nl=False)
        if result.stderr:
            click.echo(result.stderr, nl=False, err=True)
        if result.returncode:
            raise click.exceptions.Exit(result.returncode)
        return
    with _get_client() as client:
        try:
            results = client.search(query, search_type=search_type, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Search failed: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info(f'No results for "{query}"')
            return

        for idx, item in enumerate(data, 1):
            obj = item.get("object", item)
            item_type = item.get("type", obj.get("type", "—"))
            item_id = str(obj.get("id", "—"))
            title = strip_html(obj.get("title", obj.get("name", "—")))

            console.print()
            console.print(f"[title]  {idx}. [{item_type}] {title}  [/title]")
            console.print(f"  [dim]ID: {item_id}[/dim]")

            # pick useful info snippet
            if "follower_count" in obj:
                console.print(f"  {format_count(obj['follower_count'])} followers")
            elif "excerpt" in obj:
                console.print(f"  {strip_html(obj['excerpt'])}")
            elif "answer_count" in obj:
                console.print(f"  {format_count(obj['answer_count'])} answers")

            # Show answers for answer/question type results
            if answers > 0 and item_type == "search_result" and item_id != "—":
                q_id = obj.get("question", {}).get("id", item_id)
                try:
                    ans_result = client.get_question_answers(
                        str(q_id), limit=answers,
                    )
                    ans_data = ans_result.get("data", [])
                except Exception:
                    ans_data = []

                if ans_data:
                    for a in ans_data:
                        a_author = a.get("author", {}).get("name", "—")
                        a_content = strip_html(a.get("excerpt", a.get("content", "")))
                        a_upvotes = format_count(a.get("voteup_count", 0))
                        console.print(
                            f"    [dim]{a_author}:[/dim] {a_content}  "
                            f"[dim]{a_upvotes} upvotes[/dim]"
                        )

        console.print()


@click.command()
@click.option("-l", "--limit", default=50, help="Number of hot questions", show_default=True)
@click.option("-a", "--answers", default=3, help="Answers per question (0=hide)", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def hot(limit: int, answers: int, as_json: bool):
    """Show trending questions (热榜)."""
    with _get_client() as client:
        try:
            results = client.get_hot_list(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch hot list: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("Hot list is empty")
            return

        for idx, item in enumerate(data, 1):
            target = item.get("target", item.get("question", item))
            title = strip_html(target.get("title", "—"))
            q_id = target.get("id", "")
            reaction = item.get("reaction", {})
            heat = item.get("detail_text", "")
            if not heat:
                pv = reaction.get("pv", reaction.get("new_pv", 0))
                heat = format_count(pv) + " views" if pv else "—"

            console.print()
            console.print(f"[title]  {idx}. {title}  [/title]")
            console.print(f"  [dim]{heat}[/dim]")

            if answers > 0 and q_id:
                try:
                    ans_result = client.get_question_answers(
                        str(q_id), limit=answers,
                    )
                    ans_data = ans_result.get("data", [])
                except Exception:
                    ans_data = []

                if ans_data:
                    for a in ans_data:
                        a_author = a.get("author", {}).get("name", "—")
                        a_excerpt = strip_html(a.get("excerpt", a.get("content", "")))
                        a_upvotes = format_count(a.get("voteup_count", 0))
                        console.print(
                            f"    [dim]{a_author}:[/dim] {a_excerpt}  "
                            f"[dim]{a_upvotes} upvotes[/dim]"
                        )
                else:
                    console.print("    [dim]No answers[/dim]")

        console.print()


@click.command()
@click.argument("question_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def question(question_id: int, as_json: bool):
    """View question details."""
    with _get_client() as client:
        try:
            q = client.get_question(question_id)
        except Exception as e:
            print_error(f"Failed to fetch question: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(q, indent=2, ensure_ascii=False))
            return

        title = strip_html(q.get("title", "—"))
        detail = strip_html(q.get("detail", "—"))

        console.print()
        console.print(f"[title]  {title}  [/title]")
        console.print()
        if detail and detail != "—":
            console.print(detail)
            console.print()

        stats = format_stats_line({
            "Answers": q.get("answer_count", 0),
            "Followers": q.get("follower_count", 0),
            "Views": q.get("visit_count", 0),
        })
        console.print(stats)
        console.print()


@click.command()
@click.argument("question_id", type=int)
@click.option("-l", "--limit", default=5, help="Number of answers", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--sort", "sort_by", default="default",
              type=click.Choice(["default", "created"]),
              help="Sort order")
def answers(question_id: int, limit: int, as_json: bool, sort_by: str):
    """List answers for a question."""
    with _get_client() as client:
        try:
            results = client.get_question_answers(question_id, limit=limit, sort_by=sort_by)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch answers: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No answers yet")
            return

        table = make_table(f" Answers — Q{question_id} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Author", width=14)
        table.add_column("Excerpt", ratio=1)
        table.add_column("Upvotes", width=10, justify="right")

        for i, ans in enumerate(data, 1):
            author = ans.get("author", {}).get("name", "Anonymous")
            excerpt = strip_html(ans.get("excerpt", ans.get("content", "—")))
            upvotes = format_count(ans.get("voteup_count", 0))
            table.add_row(str(i), author, excerpt, f"[bold]{upvotes}[/bold]")

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.argument("answer_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("-c", "--comments", is_flag=True, help="Show comments")
@click.option("-l", "--limit", default=0, help="Number of comments (0=all)", show_default=True)
def answer(answer_id: int, as_json: bool, comments: bool, limit: int):
    """Read a specific answer."""
    with _get_client() as client:
        try:
            ans = client.get_answer(answer_id)
        except Exception as e:
            print_error(f"Failed to fetch answer: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(ans, indent=2, ensure_ascii=False))
            return

        author = ans.get("author", {}).get("name", "Anonymous")
        content = strip_html(ans.get("content", "—"))

        console.print()
        console.print(f"[title]  Answer by {author}  [/title]")
        console.print()
        console.print(content)
        console.print()

        stats = format_stats_line({
            "Upvotes": ans.get("voteup_count", 0),
            "Comments": ans.get("comment_count", 0),
        })
        console.print(stats)
        console.print()

        if comments:
            try:
                if limit <= 0:
                    # Fetch all comments via pagination
                    all_comments = []
                    offset = 0
                    page_size = 20
                    while True:
                        result = client.get_answer_comments(
                            str(answer_id), offset=offset, limit=page_size,
                        )
                        c_data = result.get("data", [])
                        all_comments.extend(c_data)
                        paging = result.get("paging", {})
                        if paging.get("is_end", True) or not c_data:
                            break
                        offset += len(c_data)
                    c_data = all_comments
                else:
                    result = client.get_answer_comments(str(answer_id), limit=limit)
                    c_data = result.get("data", [])
            except Exception as e:
                print_error(f"Failed to fetch comments: {e}")
                return

            if not c_data:
                print_info("No comments")
                return

            for i, c in enumerate(c_data, 1):
                c_content = strip_html(c.get("content", ""))
                c_likes = format_count(c.get("vote_count", 0))
                console.print(f"  [dim]{i}.[/dim] {c_content}  [dim]{c_likes} likes[/dim]")
            console.print()


@click.command()
@click.option("-l", "--limit", default=10, help="Number of items", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def feed(limit: int, as_json: bool):
    """Show recommended feed (推荐)."""
    with _get_client() as client:
        try:
            results = client.get_feed(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch feed: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("Feed is empty")
            return

        table = make_table(" Recommended Feed ")
        table.add_column("ID", style="dim", min_width=12)
        table.add_column("Type", width=8)
        table.add_column("Title / Excerpt", ratio=1)
        table.add_column("Author", width=14)

        for item in data:
            target = item.get("target", {})
            item_type = target.get("type", "—")
            item_id = str(target.get("id", "—"))
            title = strip_html(
                target.get("title", "")
                or target.get("question", {}).get("title", "")
                or strip_html(target.get("excerpt", "—"))
            )
            author = target.get("author", {}).get("name", "—")
            table.add_row(item_id, item_type, title, author)

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.option("-l", "--limit", default=6, help="Number of feed items", show_default=True)
@click.option(
    "-c", "--comment-limit", default=10,
    help="Comments per item (0=hide)", show_default=True,
)
def feeds(limit: int, comment_limit: int):
    """Show recommended feed with comments (推荐+评论)."""
    with _get_client() as client:
        try:
            results = client.get_feed(limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch feed: {e}")
            sys.exit(1)

        if not data:
            print_info("Feed is empty")
            return

        for idx, item in enumerate(data, 1):
            target = item.get("target", {})
            item_type = target.get("type", "—")
            item_id = str(target.get("id", "—"))
            title = strip_html(
                target.get("title", "")
                or target.get("question", {}).get("title", "")
                or strip_html(target.get("excerpt", "—"))
            )
            author = target.get("author", {}).get("name", "—")

            console.print()
            console.print(
                f"[title]  {idx}. [{item_type}] {title}  [/title]"
            )
            console.print(f"  [dim]ID: {item_id}  Author: {author}[/dim]")

            if item_type == "answer":
                try:
                    ans = client.get_answer(item_id)
                    content = strip_html(ans.get("content", ""))
                except Exception:
                    content = strip_html(target.get("excerpt", ""))
            else:
                content = strip_html(target.get("content", target.get("excerpt", "")))

            if content:
                console.print(f"  {content}")

            if comment_limit > 0 and item_type == "answer":
                try:
                    c_result = client.get_answer_comments(item_id, limit=comment_limit)
                    c_data = c_result.get("data", [])
                except Exception:
                    c_data = []

                if c_data:
                    for i, c in enumerate(c_data, 1):
                        c_content = strip_html(c.get("content", ""))
                        c_likes = format_count(c.get("vote_count", 0))
                        console.print(
                            f"    [dim]{i}.[/dim] {c_content}  [dim]{c_likes} likes[/dim]"
                        )
                else:
                    console.print("    [dim]No comments[/dim]")

        console.print()


@click.command()
@click.argument("topic_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def topic(topic_id: int, as_json: bool):
    """View topic details and hot questions."""
    with _get_client() as client:
        try:
            t = client.get_topic(topic_id)
        except Exception as e:
            print_error(f"Failed to fetch topic: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(t, indent=2, ensure_ascii=False))
            return

        name = t.get("name", "—")
        intro = strip_html(t.get("introduction", ""))

        console.print()
        console.print(f"[title]  # {name}  [/title]")
        if intro:
            console.print()
            console.print(intro)

        stats = format_stats_line({
            "Followers": t.get("followers_count", 0),
            "Questions": t.get("questions_count", 0),
        })
        console.print()
        console.print(stats)

        # Hot questions under this topic
        try:
            hot_q = client.get_topic_hot_questions(topic_id, limit=10)
            q_data = hot_q.get("data", [])
        except Exception:
            q_data = []

        if q_data:
            table = make_table(" Hot Questions ")
            table.add_column("#", style="dim", width=4)
            table.add_column("Question", ratio=1)
            table.add_column("Answers", width=10, justify="right")

            for i, item in enumerate(q_data, 1):
                q_title = strip_html(item.get("title", "—"))
                q_answers = format_count(item.get("answer_count", 0))
                table.add_row(str(i), q_title, q_answers)

            console.print()
            console.print(table)

        console.print()
