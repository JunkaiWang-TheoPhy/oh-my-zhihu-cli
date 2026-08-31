"""The full-screen, keyboard-driven console used by ``zhihu``."""

from __future__ import annotations

import contextlib
import curses
import io
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

WORKSPACES = (
    ("首页", ""),
    ("推荐", "feed"),
    ("热榜", "hot"),
    ("搜索", "search"),
    ("写作", "pin"),
    ("草稿", "drafts"),
    ("账号", "account list"),
    ("帮助", "guidance"),
)
ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
ASSET_DIR = Path(__file__).with_name("assets")


class _StdoutProxy:
    """Keep Rich attached to the caller's current stdout (including pytest)."""

    def write(self, value: str) -> int:
        return sys.stdout.write(value)

    def flush(self) -> None:
        sys.stdout.flush()

    def isatty(self) -> bool:
        return sys.stdout.isatty()


@dataclass
class ConsoleState:
    """State for the persistent workbench, independent of curses."""

    active_index: int = 0
    command_line: str = ""
    messages: list[str] = field(default_factory=lambda: [
        "欢迎来到知乎工作台。",
        "按 : 输入命令，Enter 在当前工作区执行；按 q 退出。",
    ])
    readonly: bool = False
    backend: str | None = None
    account: str | None = None
    session_account: str | None = None
    api_account: str | None = None

    @property
    def active_name(self) -> str:
        return WORKSPACES[self.active_index][0]

    @property
    def active_command(self) -> str:
        return WORKSPACES[self.active_index][1]

    def move_to(self, index: int) -> None:
        self.active_index = max(0, min(index, len(WORKSPACES) - 1))

    def command_args(self) -> list[str]:
        try:
            return shlex.split(self.command_line)
        except ValueError as exc:
            self.messages = [f"命令解析失败：{exc}"]
            return []


def _display_width(text: str) -> int:
    """Approximate terminal width without adding a dependency."""
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(char) in "WFA" else 1 for char in text)


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    result = []
    used = 0
    for char in text:
        char_width = 2 if _display_width(char) == 2 else 1
        if used + char_width > width:
            break
        result.append(char)
        used += char_width
    return "".join(result) + " " * max(0, width - used)


def _panel_line(left: str, right: str, sidebar: int, main: int) -> str:
    return "│" + _fit(left, sidebar) + "│" + _fit(right, main) + "│"


def render_frame(state: ConsoleState, *, width: int, height: int) -> str:
    """Render one complete workbench frame; output never escapes this frame."""
    width = max(width, 60)
    height = max(height, 16)
    inner = width - 2
    sidebar = min(25, max(20, inner // 4))
    main = inner - sidebar - 1
    lines = [
        "╭" + "─" * inner + "╮",
        "│" + _fit(" 知乎工作台  ·  全屏终端控制台", inner) + "│",
        _panel_line(" 工作区", " " + state.active_name, sidebar, main),
        "├" + "─" * sidebar + "┼" + "─" * main + "┤",
    ]
    # Reserve a clean brand strip; shrink it on small terminals so the title
    # and command bar never scroll out of the frame.
    brand_rows = min(8, max(0, height - 22))
    for _ in range(brand_rows):
        lines.append(_panel_line("", "", sidebar, main))
    lines.append(_panel_line("─" * sidebar, "─" * main, sidebar, main))
    for index, (name, command) in enumerate(WORKSPACES):
        marker = "▸" if index == state.active_index else " "
        lines.append(_panel_line(f" {marker} {name}", f" {command or 'workbench'}", sidebar, main))
        if index == 3:
            lines.append(_panel_line("─" * sidebar, "", sidebar, main))

    lines.append("├" + "─" * sidebar + "┼" + "─" * main + "┤")
    # Six rows are reserved below the output pane: spacer, divider, status,
    # key hints, command input, and the bottom border.
    output_height = max(0, height - len(lines) - 10)
    output = state.messages[-output_height:]
    for message in output:
        lines.append(_panel_line("", " " + message, sidebar, main))
    for _ in range(output_height - len(output)):
        lines.append(_panel_line("", "", sidebar, main))
    lines.extend([
        _panel_line("", "", sidebar, main),
        _panel_line("", " 浏览  ·  阅读  ·  写作  ·  管理", sidebar, main),
        "├" + "─" * sidebar + "┴" + "─" * main + "┤",
        "│" + _fit(
            f" {'READONLY' if state.readonly else 'READ/WRITE'} · "
            f"{(state.backend or 'auto').upper()} · "
            f"Session:{state.session_account or 'none'} · "
            f"Official API:{state.api_account or 'system'}",
            inner,
        ) + "│",
        "│" + _fit(" ↑↓/j/k 导航   1-8 切换   : 命令   Enter 执行   q 退出", inner) + "│",
        "│" + _fit(f" 命令 > {state.command_line}", inner) + "│",
        "╰" + "─" * inner + "╯",
    ])
    return "\n".join(lines[-height:])


def run_tui(
    *,
    readonly: bool = False,
    backend: str | None = None,
    account: str | None = None,
) -> None:
    """Run the persistent console, with a safe fallback for dumb terminals."""
    try:
        curses.wrapper(
            lambda screen: _main(
                screen,
                readonly=readonly,
                backend=backend,
                account=account,
            )
        )
    except (curses.error, OSError):
        from .display import print_banner

        print_banner()


def _main(screen, *, readonly: bool, backend: str | None, account: str | None) -> None:
    from .accounts import get_account_store

    store = get_account_store()
    state = ConsoleState(
        readonly=readonly,
        backend=backend,
        account=account,
        session_account=account or store.active_name("session"),
        api_account=account or store.active_name("api"),
    )
    screen.keypad(True)
    try:
        curses.start_color()
        curses.use_default_colors()
        # xterm-256 colour 33 is the closest portable terminal colour to
        # Zhihu's brand blue (#0084ff); COLOR_BLUE is rendered purple on macOS.
        curses.init_pair(1, 33 if curses.COLORS >= 256 else curses.COLOR_CYAN, -1)
        blue = curses.color_pair(1)
    except curses.error:
        blue = 0
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    while True:
        screen.erase()
        frame = render_frame(state, width=screen.getmaxyx()[1], height=screen.getmaxyx()[0])
        for row, line in enumerate(frame.splitlines()):
            try:
                screen.addstr(row, 0, line[: screen.getmaxyx()[1] - 1], blue)
            except curses.error:
                pass
        if screen.getmaxyx()[0] >= 30:
            _draw_brand_assets(screen, sidebar=min(25, max(20, (screen.getmaxyx()[1] - 3) // 4)))
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            state.move_to(state.active_index + 1)
        elif key in (curses.KEY_UP, ord("k")):
            state.move_to(state.active_index - 1)
        elif ord("1") <= key <= ord(str(len(WORKSPACES))):
            state.move_to(key - ord("1"))
        elif key == ord(":"):
            state.command_line = _read_command(screen, "")
        elif key in (curses.KEY_ENTER, 10, 13):
            needs_input = state.active_command in {"ask", "pin", "article", "search"}
            bare_command = state.command_line.strip() in {"", state.active_command}
            if needs_input and bare_command:
                entered = _read_command(screen, "")
                state.command_line = f"{state.active_command} {entered}".strip()
            else:
                _execute_selected(state)


def _read_command(screen, default: str) -> str:
    curses.echo()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    screen.move(screen.getmaxyx()[0] - 2, 10)
    screen.clrtoeol()
    screen.addstr("命令 > " + default)
    value = screen.getstr().decode("utf-8", errors="replace")
    curses.noecho()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    return value or default


def _draw_brand_assets(screen, *, sidebar: int) -> None:
    """Paint bundled brand sprites into the reserved strip."""
    try:
        _draw_sprite(screen, ASSET_DIR / "logo_01.png", sidebar + 3, 5, width=22)
        _draw_sprite(screen, ASSET_DIR / "liukanshan_01.png", sidebar + 34, 4, width=16)
    except (OSError, curses.error):
        return


def _draw_sprite(screen, path: Path, x: int, y: int, *, width: int) -> None:
    image = Image.open(path).convert("RGBA")
    height = max(1, round(image.height * width / image.width / 2))
    image = image.resize((width, height * 2), Image.Resampling.NEAREST)
    pair_cache: dict[tuple[int, int, int], int] = {}
    next_pair = 2

    def colour(rgb: tuple[int, int, int]) -> int:
        nonlocal next_pair
        if rgb not in pair_cache and next_pair < curses.COLOR_PAIRS:
            pair_cache[rgb] = next_pair
            curses.init_pair(next_pair, _nearest_colour(rgb), -1)
            next_pair += 1
        return curses.color_pair(pair_cache.get(rgb, 1))

    for row in range(0, image.height, 2):
        for column in range(image.width):
            top = image.getpixel((column, row))
            bottom = image.getpixel((column, min(row + 1, image.height - 1)))
            top_rgb = top[:3] if top[3] > 24 else None
            bottom_rgb = bottom[:3] if bottom[3] > 24 else None
            if top_rgb is None and bottom_rgb is None:
                char, attr = " ", 0
            elif top_rgb is None:
                char, attr = "▄", colour(bottom_rgb)
            elif bottom_rgb is None:
                char, attr = "▀", colour(top_rgb)
            else:
                char, attr = "▀", colour(top_rgb)
            screen.addstr(y + row // 2, x + column, char, attr)


def _nearest_colour(rgb: tuple[int, int, int]) -> int:
    """Map RGB to xterm-256 without emitting raw truecolor escape codes."""
    r, g, b = rgb
    if max(rgb) - min(rgb) < 18:
        return 255 if sum(rgb) > 450 else 16
    cube = tuple(round(channel / 255 * 5) for channel in rgb)
    return 16 + 36 * cube[0] + 6 * cube[1] + cube[2]


def _execute_selected(state: ConsoleState) -> None:
    """Execute inside the workbench and retain output in its central pane."""
    args = state.command_args() or ([state.active_command] if state.active_command else [])
    requires_argument = state.active_command in {"ask", "pin", "article", "search"}
    if requires_argument and args == [state.active_command]:
        return
    if not args:
        # 首页 is the dashboard itself; Enter should not produce a fake CLI error.
        return
    global_args = []
    if state.readonly:
        global_args.append("--readonly")
    if state.backend in {"api", "session"}:
        global_args.append(f"--{state.backend}")
    if state.account:
        global_args.extend(["--account", state.account])
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    command_failed = False
    state.messages.append(f"$ {' '.join([*global_args, *args])}")
    try:
        from . import display
        from .cli import cli

        rich_console = display.console
        rich_console.file = captured_out
        try:
            with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
                cli.main([*global_args, *args], standalone_mode=False)
        finally:
            # Keep Rich dynamic: click/capsys/IDE consoles may replace stdout.
            rich_console.file = _StdoutProxy()
    except (SystemExit, KeyboardInterrupt) as exc:
        command_failed = True
        state.messages.append(f"命令结束：{exc}")
    except Exception as exc:  # Keep the UI alive when a command reports an error.
        command_failed = True
        state.messages.append(f"命令错误：{exc}")
    output = _clean_output(captured_out.getvalue() + captured_err.getvalue())
    state.messages.extend(output or ([] if command_failed else ["命令已执行，无输出。"]))
    state.command_line = ""


def _clean_output(value: str) -> list[str]:
    """Turn Rich/Click output into plain lines safe for a curses cell grid."""
    value = ANSI_ESCAPE.sub("", value).replace("\r", "")
    return [line.expandtabs(2) for line in value.splitlines()]
