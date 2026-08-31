"""Terminal display utilities for zhihu-cli.

Provides a consistent visual theme for all CLI output.
Uses Rich library for professional terminal rendering.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

from PIL import Image
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Theme ──────────────────────────────────────────────────────────────────────

ZHIHU_THEME = Theme({
    "info": "dim cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "title": "bold cyan",
    "subtitle": "dim white",
    "accent": "bold blue",
    "muted": "dim",
    "stat.key": "cyan",
    "stat.value": "white",
    "badge": "bold magenta",
})

console = Console(theme=ZHIHU_THEME)
ASSET_DIR = Path(__file__).with_name("assets")

# ── Brand ──────────────────────────────────────────────────────────────────────

BRAND = "[bold #0084ff]知[/bold #0084ff][bold white]乎[/bold white] [dim]CLI[/dim]"
SEPARATOR = "[dim]─" * 50 + "[/dim]"

PIXEL_FOX = (
    "...B....B...",
    "..BBB..BBB..",
    ".BBBBBBBBBB.",
    "BBWWWWWWWWBB",
    "BWWDWWDWWWWB",
    "BWWWWWWWWWWB",
    "BWWWWWYWWWWB",
    ".BWWWWWWWWB.",
    "..BBBBBBBB..",
    "...BB..BB...",
)


def render_sprite(name: str, *, width: int = 18) -> Text:
    """Render an embedded PNG sprite with terminal half-block cells."""
    path = ASSET_DIR / f"{name}.png"
    if not path.is_file():
        raise FileNotFoundError(path)
    image = Image.open(path).convert("RGBA")
    height = max(1, round(image.height * width / image.width / 2))
    image = image.resize((width, height * 2), Image.Resampling.NEAREST)
    text = Text()
    for y in range(0, image.height, 2):
        if y:
            text.append("\n")
        for x in range(image.width):
            top = image.getpixel((x, y))
            bottom = image.getpixel((x, min(y + 1, image.height - 1)))
            top_color = _pixel_color(top)
            bottom_color = _pixel_color(bottom)
            if top_color is None and bottom_color is None:
                text.append("  ")
            elif top_color is None:
                text.append("▄", style=Style(color=bottom_color))
            elif bottom_color is None:
                text.append("▀", style=Style(color=top_color))
            else:
                text.append("▀", style=Style(color=top_color, bgcolor=bottom_color))
    return text


def _pixel_color(pixel: tuple[int, int, int, int]) -> str | None:
    red, green, blue, alpha = pixel
    if alpha < 24:
        return None
    return f"#{red:02x}{green:02x}{blue:02x}"


def render_pixel_fox() -> Text:
    """Return a stable pixel-art Liu Kan-shan face independent of terminal image support."""
    colors = {"B": "#0084ff", "W": "#f5f7fa", "D": "#172b4d", "Y": "#ffcc66"}
    text = Text()
    for row_index, row in enumerate(PIXEL_FOX):
        if row_index:
            text.append("\n")
        for pixel in row:
            if pixel == ".":
                text.append("  ")
            else:
                text.append("█", style=colors[pixel])
    return text


def print_banner():
    """Print a compact, local-only Zhihu workbench."""
    ver = _get_version()
    from .config import COOKIE_FILE
    from .official import get_official_cli_path
    from .routing import load_settings

    settings = load_settings()
    session_state = "已配置" if COOKIE_FILE.exists() else "未配置"
    api_state = "已安装" if get_official_cli_path().is_file() else "未安装"

    status = Table.grid(padding=(0, 1))
    status.add_column(style="bold #0084ff", width=12)
    status.add_column(style="white")
    status.add_row("SESSION", session_state)
    status.add_row("OFFICIAL API", api_state)
    status.add_row("优先后端", settings["priority"])
    status.add_row("语言", settings["language"])

    sections = Table.grid(padding=(0, 2))
    sections.add_column(style="bold white", width=8)
    sections.add_column(style="dim white")
    sections.add_row("浏览", "feed · hot · search · question")
    sections.add_row("阅读", "answer · answers · user · collections")
    sections.add_row("写作", "pin · article · ask · drafts")
    sections.add_row("设置", "config show · login · status")

    right = Table.grid(padding=(0, 0))
    right.add_row(Text.from_markup(f"{BRAND}  [dim]v{ver}[/dim]"))
    right.add_row(Text("知乎终端工作台", style="white"))
    right.add_row(Text(""))
    right.add_row(status)
    left = Table.grid(padding=(0, 0))
    left.add_row(Text("知乎", style="bold #0084ff"))
    left.add_row(Text("知乎蓝 · terminal", style="dim"))
    left.add_row(Text(""))
    left.add_row(render_pixel_fox())

    top = Table.grid(padding=(0, 3))
    top.add_column(width=18)
    top.add_column()
    top.add_row(left, right)

    layout = Table.grid(padding=(0, 0))
    layout.add_row(top)
    layout.add_row(Text(""))
    layout.add_row(sections)
    console.print(
        Panel(
            layout,
            border_style="#0084ff",
            box=box.DOUBLE,
            padding=(1, 2),
            title="[bold #0084ff]知乎 · 工作台[/bold #0084ff]",
            subtitle="[dim]Search · Read · Write · Manage[/dim]",
        ),
        highlight=False,
    )


def _get_version() -> str:
    from . import __version__
    return __version__


# ── Message helpers ────────────────────────────────────────────────────────────

def print_success(msg: str):
    """Print a success message."""
    console.print(f"  [success]✓[/success] {msg}")


def print_error(msg: str):
    """Print an error message."""
    console.print(f"  [error]✗[/error] {msg}")


def print_warning(msg: str):
    """Print a warning message."""
    console.print(f"  [warning]![/warning] {msg}")


def print_info(msg: str):
    """Print an informational message."""
    console.print(f"  [info]›[/info] {msg}")


def print_hint(msg: str):
    """Print a hint/tip message."""
    console.print(f"  [muted]hint: {msg}[/muted]")


# ── Text utilities ─────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def format_count(count: int | str) -> str:
    """Format large numbers for display (e.g. 12345 → 1.2万)."""
    if isinstance(count, str):
        try:
            count = int(count)
        except ValueError:
            return str(count)
    if count >= 100_000_000:
        return f"{count / 100_000_000:.1f}亿"
    if count >= 10_000:
        return f"{count / 10_000:.1f}万"
    return str(count)


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


# ── Table factories ────────────────────────────────────────────────────────────

def make_table(title: str, *, show_lines: bool = False, pad_edge: bool = False) -> Table:
    """Create a branded Table with standard styling."""
    return Table(
        title=f"[title]{title}[/title]",
        title_style="",
        border_style="#0084ff",
        header_style="bold cyan",
        show_lines=show_lines,
        pad_edge=pad_edge,
        expand=False,
    )


def make_kv_table(title: str) -> Table:
    """Create a key-value profile table."""
    table = Table(
        title=f"[title]{title}[/title]",
        title_style="",
        border_style="#0084ff",
        show_header=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("Key", style="stat.key", width=12, justify="right")
    table.add_column("Value", style="stat.value")
    return table


# ── Stats display ──────────────────────────────────────────────────────────────

def format_stats_line(pairs: dict[str, str | int]) -> str:
    """Create an inline stats display like '▸ 1.2万 Answers  ▸ 500 Followers'."""
    parts = []
    for label, value in pairs.items():
        parts.append(f"[dim]▸[/dim] [white]{format_count(value)}[/white] [dim]{label}[/dim]")
    return "  ".join(parts)
