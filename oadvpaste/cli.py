"""omarchy-advanced-paste — transform the clipboard on its way into the window.

    omarchy-advanced-paste                 open the menu
    omarchy-advanced-paste markdown        apply one transform and paste it
    omarchy-advanced-paste ai "as a table" ask the agent for anything else
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

from . import ai, clipboard, menu
from . import __version__
from .transforms import BY_NAME, CATALOGUE, GROUPS, Clip, TransformError, apply

# Shown under each entry in the menu; also what the picker gives back, so it
# doubles as the key that maps a pick to a transform.
HINTS = {
    "plain": "Drop every bit of formatting",
    "markdown": "Rich text to Markdown",
    "unwrap": "Join hard-wrapped lines into paragraphs",
    "trim": "Trailing spaces and extra blank lines",
    "single-line": "Everything on one line",
    "quote": "Prefix every line with >",
    "bullets": "One line, one bullet",
    "numbered": "One line, one number",
    "code-block": "Wrap in a fenced code block",
    "json": "Pretty-print, two-space indent",
    "json-min": "Strip every space",
    "json-to-csv": "Array of objects to CSV",
    "csv-to-table": "CSV or spreadsheet cells to a Markdown table",
    "csv-to-json": "CSV to an array of objects",
    "escape-json": "As a quoted JSON string",
    "upper": "ALL CAPS",
    "lower": "all lowercase",
    "title": "Capitalise Every Word",
    "sentence": "Only the first letter",
    "unaccent": "acao instead of ação",
    "slug": "lowercase-with-hyphens",
    "snake": "lowercase_with_underscores",
    "camel": "camelCaseLikeThis",
    "sort": "Alphabetically, case-insensitive",
    "unique": "Keep the first of each line",
    "reverse-lines": "Last line first",
    "base64": "Encode as Base64",
    "unbase64": "Decode from Base64",
    "urlencode": "Percent-encode",
    "urldecode": "Undo percent-encoding",
    "url-params": "One query parameter per line",
    "sha256": "Hex digest of the text",
    "count": "Characters, words, lines, bytes",
}

AI_LABEL = "Transform with AI…"
AI_HINT = "Describe what you want in your own words"

# One Nerd Font glyph per group, the way the rest of Omarchy's menus label their rows.
ICONS = {
    "Formatting": "",      # align-left
    "Data": "",            # database
    "Case": "",            # font
    "Lines": "",           # list
    "Encoding": "",        # code
    "AI": "",              # bolt
}


def build_menu() -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    """Rows for omarchy-menu-select, which reads them as "glyph⇥label⇥subtext".

    All three fields have to be there: hand it two and the first is taken for the
    glyph, which draws the label into the icon column on top of the subtext. The
    picker returns "label⇥subtext", so that pair is the key back to the transform.
    """
    rows: list[tuple[str, str, str]] = []
    keys: dict[str, str] = {}
    for group in GROUPS:
        for t in CATALOGUE:
            if t.group != group:
                continue
            hint = f"{group} · {HINTS.get(t.name, t.name)}"
            rows.append((ICONS.get(group, ""), t.label, hint))
            keys[f"{t.label}\t{hint}"] = t.name
    hint = f"AI · {AI_HINT}"
    rows.append((ICONS["AI"], AI_LABEL, hint))
    keys[f"{AI_LABEL}\t{hint}"] = "ai"
    return rows, keys


def deliver(text: str, args) -> int:
    """Where a result goes: stdout when asked, otherwise the clipboard and the window."""
    if args.stdout:
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    clipboard.write(text)
    if not args.copy_only:
        clipboard.paste_into_focused()
    return 0


def read_clip(args) -> Clip:
    if args.stdin:
        return Clip(text=sys.stdin.read())
    if not clipboard.available():
        raise TransformError("wl-clipboard is not installed (wl-paste / wl-copy)")
    return clipboard.read()


def cmd_list(args) -> int:
    width = max(len(t.name) for t in CATALOGUE)
    for group in GROUPS:
        print(f"\n{group}")
        for t in CATALOGUE:
            if t.group == group:
                alias = f"  (also: {', '.join(t.aliases)})" if t.aliases else ""
                print(f"  {t.name:<{width}}  {HINTS.get(t.name, '')}{alias}")
    print("\nAI\n  ai" + " " * (width - 2) + "  Describe the transform in your own words")
    return 0


def cmd_ai(args) -> int:
    clip = read_clip(args)
    if not clip.text.strip():
        menu.notify("Advanced paste", "The clipboard is empty")
        return 1
    instruction = args.instruction or menu.ask("Transform the clipboard how?")
    if not instruction:
        return 1
    try:
        out = ai.transform(clip.text, instruction)
    except ai.AIError as e:
        menu.notify("Advanced paste", str(e))
        print(f"omarchy-advanced-paste: {e}", file=sys.stderr)
        return 1
    return deliver(out, args)


def cmd_file(args) -> int:
    """PowerToys' "paste as file": park the clipboard in a file and hand over its path."""
    target_dir = os.path.expanduser(args.dir or "~/Downloads")
    os.makedirs(target_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    image = None if args.stdin else clipboard.read_image()
    if image:
        ext, data = image
        path = os.path.join(target_dir, f"clipboard-{stamp}.{ext}")
        with open(path, "wb") as f:
            f.write(data)
    else:
        clip = read_clip(args)
        if not clip.text.strip():
            menu.notify("Advanced paste", "The clipboard is empty")
            return 1
        ext = "md" if clip.rich else "txt"
        path = os.path.join(target_dir, f"clipboard-{stamp}.{ext}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(clip.text if not clip.rich else clip.text)

    if args.stdout:
        print(path)
        return 0
    clipboard.write_uri_list([path])
    menu.notify("Saved to a file", path)
    return 0


def cmd_setup(args) -> int:
    """Offer the keybinding, without ever editing a line the user wrote."""
    path = os.path.expanduser("~/.config/hypr/bindings.lua")
    line = 'o.bind("SUPER + SHIFT + V", "Advanced paste", "omarchy-advanced-paste")'
    try:
        with open(path, encoding="utf-8") as f:
            current = f.read()
    except OSError:
        current = ""
    if "omarchy-advanced-paste" in current:
        print(f"The keybinding is already in {path}")
        return 0
    print(f"Add this line to {path}:\n\n  {line}\n")
    if not args.yes:
        try:
            if input("Add it now? [y/N] ").strip().lower() not in ("y", "yes"):
                return 0
        except (EOFError, KeyboardInterrupt):
            return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(("" if current.endswith("\n") or not current else "\n")
                + "\n-- Advanced paste: transform the clipboard on the way in\n" + line + "\n")
    print(f"Added. Reload Hyprland (omarchy-refresh-hyprland) to pick it up.")
    return 0


def cmd_menu(args) -> int:
    clip = read_clip(args)
    if not clip.text.strip() and not clip.rich:
        image = clipboard.read_image()
        if image:
            return cmd_file(args)
        menu.notify("Advanced paste", "The clipboard is empty")
        return 1
    rows, keys = build_menu()
    pick = menu.select("Advanced paste", rows, width=640)
    if not pick:
        return 1
    name = keys.get(pick)
    if name is None:                       # a picker that returns the label alone
        name = keys.get(next((k for k in keys if k.split("\t")[0] == pick.split("\t")[0]), ""), None)
    if name is None:
        return 1
    if name == "ai":
        args.instruction = None
        return cmd_ai(args)
    return run_transform(name, clip, args)


def run_transform(name: str, clip: Clip, args) -> int:
    try:
        out = apply(name, clip)
    except TransformError as e:
        menu.notify("Advanced paste", str(e))
        print(f"omarchy-advanced-paste: {e}", file=sys.stderr)
        return 1
    return deliver(out, args)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="omarchy-advanced-paste",
        description="Transform the clipboard on its way into the window.",
        epilog="With no transform, the Omarchy menu opens with every one of them.")
    p.add_argument("transform", nargs="?", help="a transform name, 'ai', 'file', 'list' or 'setup'")
    p.add_argument("instruction", nargs="?", help="for 'ai': what to do, in your own words")
    p.add_argument("-c", "--copy-only", action="store_true",
                   help="leave the result on the clipboard without pasting it")
    p.add_argument("-o", "--stdout", action="store_true",
                   help="print the result instead of touching the clipboard")
    p.add_argument("-i", "--stdin", action="store_true",
                   help="read the input from stdin instead of the clipboard")
    p.add_argument("--dir", help="for 'file': where to save (default ~/Downloads)")
    p.add_argument("-y", "--yes", action="store_true", help="for 'setup': don't ask")
    p.add_argument("-V", "--version", action="version", version=f"omarchy-advanced-paste {__version__}")
    args = p.parse_args(argv)

    name = args.transform
    if name is None:
        return cmd_menu(args)
    if name == "list":
        return cmd_list(args)
    if name == "setup":
        return cmd_setup(args)
    if name == "ai":
        return cmd_ai(args)
    if name == "file":
        return cmd_file(args)
    if name not in BY_NAME:
        print(f"omarchy-advanced-paste: unknown transform '{name}'. "
              f"Try `omarchy-advanced-paste list`.", file=sys.stderr)
        return 2
    return run_transform(BY_NAME[name].name, read_clip(args), args)


if __name__ == "__main__":
    sys.exit(main())
