# Advanced Paste for Omarchy

Transform the clipboard on its way into the window. A port of the idea behind
[PowerToys Advanced Paste](https://learn.microsoft.com/windows/powertoys/advanced-paste)
to [Omarchy](https://omarchy.org) — built on Omarchy's own menu, themed like the rest of
the system, and with the AI transform wired to the coding agent you already use.

**`SUPER + SHIFT + V`** opens the menu. Pick a transform, and the result is pasted into
whatever window you were in.

*[Leia em português](README.pt-BR.md)*

## What it does

Copy anything, then paste it as something else:

| Group | Transforms |
|---|---|
| **Formatting** | plain text · Markdown (from rich text) · unwrap hard-wrapped paragraphs · trim whitespace · single line · Markdown quote · bullet list · numbered list · fenced code block |
| **Data** | JSON formatted · JSON minified · JSON → CSV · CSV → Markdown table · CSV → JSON · escape as a JSON string |
| **Case** | UPPERCASE · lowercase · Title Case · Sentence case · remove accents · kebab-slug · snake_case · camelCase |
| **Lines** | sort · remove duplicates · reverse order |
| **Encoding** | Base64 encode/decode · URL encode/decode · break a URL apart · SHA-256 · count characters and words |
| **AI** | describe the transform in your own words |

Two more that aren't transforms:

- **Paste as file** — `omarchy-advanced-paste file` parks the clipboard (text *or* image) in
  `~/Downloads` and puts the file itself on the clipboard, so the next paste lands in a file
  manager or an upload dialog. Copying an image and opening the menu does this automatically.
- **Count** — characters, words, lines and bytes, without leaving the window.

### Markdown, properly

"Paste as Markdown" reads the clipboard's `text/html` flavour — what a browser, a doc editor
or a chat app leaves behind when you copy rich text — and converts headings, emphasis, links,
images, lists, code, quotes and tables. The converter is standard-library Python: no pandoc,
no Node, nothing to install.

### The AI transform

Anything you can describe: *"turn this into a bullet list"*, *"translate to English"*,
*"write this as a commit message"*, *"extract only the e-mail addresses"*.

It runs the agent Omarchy already has configured (`omarchy default agent`) — Claude Code,
Gemini, Codex, OpenCode or Crush — with the clipboard on stdin. No extra API key, no account,
no telemetry. If you want a different command, put one in
`~/.config/omarchy-advanced-paste/config.json`:

```json
{ "ai_command": ["claude", "-p", "{prompt}"] }
```

## Install

### Arch / Omarchy

Grab the package from [Releases](https://github.com/andrebbruno/omarchy-advanced-paste/releases)
and install it:

```bash
sudo pacman -U omarchy-advanced-paste-*-any.pkg.tar.zst
omarchy-advanced-paste setup     # offers the SUPER+SHIFT+V keybinding
omarchy-refresh-hyprland
```

Or build it yourself:

```bash
git clone https://github.com/andrebbruno/omarchy-advanced-paste
cd omarchy-advanced-paste/packaging && makepkg -si
```

### Anywhere else

```bash
pipx install git+https://github.com/andrebbruno/omarchy-advanced-paste
```

Requirements: Python 3.11+, `wl-clipboard` (reading and writing the clipboard) and `wtype`
(sending the paste). Both are already on an Omarchy box. Outside Omarchy the menu falls back
to `gum`, and then to a plain numbered prompt on the terminal.

## Use

```bash
omarchy-advanced-paste                  # the menu
omarchy-advanced-paste markdown         # one transform, straight to the window
omarchy-advanced-paste json --copy-only # leave it on the clipboard, don't paste
omarchy-advanced-paste ai "as a table"  # the agent, with your own instruction
omarchy-advanced-paste file             # park the clipboard in ~/Downloads
omarchy-advanced-paste list             # every transform and its name
```

It also works as a plain filter, which is how the test suite drives it:

```bash
cat data.csv | omarchy-advanced-paste --stdin --stdout csv-to-table
```

### The keybinding

`omarchy-advanced-paste setup` appends this to `~/.config/hypr/bindings.lua` (and never
touches a line you wrote):

```lua
o.bind("SUPER + SHIFT + V", "Advanced paste", "omarchy-advanced-paste")
```

Bind single transforms too, if one of them is your daily driver:

```lua
o.bind("SUPER + ALT + V", "Paste as plain text", "omarchy-advanced-paste plain")
```

## Notes

- **Wayland only.** Reading and writing the clipboard goes through `wl-clipboard`, and the
  paste itself is a `Shift+Insert` sent with `wtype` — the same thing Omarchy's own clipboard
  scripts do, so it works in terminals and GUI apps alike.
- **Nothing leaves your machine** unless you pick the AI transform, and then only through the
  agent you configured yourself.
- **The clipboard is replaced** by the transformed text. That is the point, but it does mean
  the original is gone — Omarchy's clipboard manager (`SUPER + CTRL + V`) still has it.

## Development

```bash
python -m pytest tests -q      # 66 tests, no compositor needed
```

The transforms are pure functions over a `Clip` (text plus optional HTML) in
`oadvpaste/transforms.py`, which is what makes them testable without a Wayland session.
Adding one is a function plus a line in `CATALOGUE`.

## License

MIT © Andre Bruno
