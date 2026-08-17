"""Local backup and diff commands for read-only Zhihu draft workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click

from ..display import print_error, print_info, print_success
from .content import (
    _draft_search_text,
    _fetch_draft_pages,
    _get_client,
    _merge_paged_result,
    _write_markdown_export,
)


def _load_snapshot(path: Path) -> dict[str, dict]:
    """Load a JSON or Markdown snapshot keyed by draft ID."""
    path = path.expanduser()
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = payload.get("data", []) if isinstance(payload, dict) else payload
        return {
            str(item.get("id") or item.get("content_id")): item
            for item in data
            if isinstance(item, dict) and (item.get("id") or item.get("content_id"))
        }

    text = path.read_text(encoding="utf-8")
    records = {}
    current = None
    pending_title = None
    for line in text.splitlines():
        id_match = re.match(r"^-\s*ID[：:]\s*(\S+)", line)
        if id_match:
            current = id_match.group(1)
            records[current] = {"id": current, "title": pending_title or "（无标题）"}
            pending_title = None
            continue
        title_match = re.match(r"^##\s+(?:\d+\.\s+)?(.+)$", line)
        if title_match:
            pending_title = title_match.group(1)
    if pending_title:
        synthetic_id = f"markdown-{len(records) + 1}"
        records[synthetic_id] = {"id": synthetic_id, "title": pending_title}
    return records


def _snapshot_title(item: dict) -> str:
    return str(item.get("title") or item.get("excerpt_title") or "（无标题）")


@click.command("drafts-backup")
@click.argument("output_dir", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "-t", "--type", "draft_type", default="article",
    type=click.Choice(["article", "idea", "answer", "video"]), show_default=True,
)
@click.option("-l", "--limit", default=20, type=click.IntRange(1, 20), show_default=True)
@click.option("--all", "fetch_all", is_flag=True, help="Back up all pages")
@click.option("--search", "search_term", default="", help="Filter by title or text")
def drafts_backup(
    output_dir: Path,
    draft_type: str,
    limit: int,
    fetch_all: bool,
    search_term: str,
):
    """Back up selected drafts locally as JSON and Markdown."""
    with _get_client() as client:
        try:
            fetchers = {
                "article": client.get_article_drafts,
                "idea": client.get_drafts,
                "answer": client.get_answer_drafts,
                "video": client.get_video_drafts,
            }
            items, last_result, total = _fetch_draft_pages(
                fetchers[draft_type], limit, fetch_all,
            )
            if search_term:
                needle = search_term.casefold()
                items = [
                    item for item in items
                    if needle in _draft_search_text(draft_type, item).casefold()
                ]
                total = len(items)
            payload = (
                _merge_paged_result(last_result, items, total)
                if fetch_all
                else {"data": items, "paging": {"totals": total, "is_end": True}}
            )
            output_dir = output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / f"drafts-{draft_type}.json"
            markdown_path = output_dir / f"drafts-{draft_type}.md"
            json_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
            )
            _write_markdown_export(client, draft_type, items, markdown_path)
        except Exception as e:
            print_error(f"Failed to back up drafts: {e}")
            raise click.exceptions.Exit(1) from e

    print_success(f"Backed up {len(items)} {draft_type} drafts to {output_dir}")
    print_info(f"JSON: {json_path}")
    print_info(f"Markdown: {markdown_path}")


@click.command("drafts-diff")
@click.argument("before", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("after", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def drafts_diff(before: Path, after: Path):
    """Compare two local draft snapshots without network access."""
    try:
        before_items = _load_snapshot(before)
        after_items = _load_snapshot(after)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print_error(f"Failed to read snapshots: {e}")
        raise click.exceptions.Exit(1) from e

    added = sorted(set(after_items) - set(before_items))
    removed = sorted(set(before_items) - set(after_items))
    changed = sorted(
        draft_id for draft_id in set(before_items) & set(after_items)
        if before_items[draft_id] != after_items[draft_id]
    )

    if not (added or removed or changed):
        print_info("No changes")
        return
    for draft_id in added:
        click.echo(f"added   {draft_id}: {_snapshot_title(after_items[draft_id])}")
    for draft_id in removed:
        click.echo(f"removed {draft_id}: {_snapshot_title(before_items[draft_id])}")
    for draft_id in changed:
        click.echo(
            f"changed {draft_id}: {_snapshot_title(before_items[draft_id])}"
            f" -> {_snapshot_title(after_items[draft_id])}"
        )
