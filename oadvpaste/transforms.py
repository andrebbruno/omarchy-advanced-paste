"""The transforms themselves: pure functions over the clipboard's text.

Everything here takes a Clip and returns a string, with no side effects and no
processes spawned, so the whole catalogue is testable without a compositor.
"""
from __future__ import annotations

import ast
import base64
import binascii
import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field

from .html2md import html_to_markdown, strip_tags


@dataclass
class Clip:
    """What sits on the clipboard right now."""
    text: str = ""
    html: str | None = None

    @property
    def rich(self) -> bool:
        return bool(self.html and self.html.strip())


class TransformError(Exception):
    """The input isn't what this transform needs — reported, never a traceback."""


# ---------------------------------------------------------------- text helpers

def _lines(text: str) -> list[str]:
    return text.splitlines()


def _detect_indent(text: str) -> int:
    for line in _lines(text):
        stripped = line.lstrip(" ")
        if stripped and line != stripped:
            return len(line) - len(stripped)
    return 2


# ---------------------------------------------------------------- transforms

def t_plain(c: Clip) -> str:
    """Drop every bit of formatting, keeping only the words."""
    text = strip_tags(c.html) if c.rich else c.text
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def t_markdown(c: Clip) -> str:
    if c.rich:
        return html_to_markdown(c.html)
    # No rich flavour: the text may still be HTML someone copied as source.
    if re.search(r"<(p|div|h[1-6]|ul|ol|li|table|a|strong|em|br)\b", c.text, re.I):
        return html_to_markdown(c.text)
    raise TransformError("the clipboard has no rich text to convert")


def _loads_loose(text: str):
    """JSON first; then Python literals, which is what a debugger or log gives you."""
    text = text.strip()
    if not text:
        raise TransformError("the clipboard is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError) as e:
        raise TransformError(f"not valid JSON: {e}") from e


def t_json(c: Clip) -> str:
    return json.dumps(_loads_loose(c.text), indent=2, ensure_ascii=False, sort_keys=False)


def t_json_min(c: Clip) -> str:
    return json.dumps(_loads_loose(c.text), separators=(",", ":"), ensure_ascii=False)


def t_json_to_csv(c: Clip) -> str:
    data = _loads_loose(c.text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise TransformError("expected a JSON array of objects")
    if not data:
        raise TransformError("the array is empty")
    cols: list[str] = []
    for row in data:
        for k in row:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for row in data:
        w.writerow({k: row.get(k, "") for k in cols})
    return buf.getvalue().rstrip("\n")


def _sniff_csv(text: str) -> list[list[str]]:
    sample = text.strip()
    if not sample:
        raise TransformError("the clipboard is empty")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        if "\t" in sample.splitlines()[0]:
            dialect = csv.excel_tab
    rows = [r for r in csv.reader(io.StringIO(sample), dialect) if r]
    if not rows:
        raise TransformError("no rows found")
    return rows


def t_csv_to_table(c: Clip) -> str:
    """CSV (or a spreadsheet selection, which pastes as TSV) into a Markdown table."""
    rows = _sniff_csv(c.text)
    width = max(len(r) for r in rows)
    rows = [[cell.strip().replace("|", "\\|") for cell in r] + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "| " + " | ".join("---" for _ in range(width)) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def t_csv_to_json(c: Clip) -> str:
    rows = _sniff_csv(c.text)
    head, body = rows[0], rows[1:]
    out = [{head[i] if i < len(head) else f"col{i}": (r[i] if i < len(r) else "")
            for i in range(max(len(head), len(r)))} for r in body]
    return json.dumps(out, indent=2, ensure_ascii=False)


def t_upper(c: Clip) -> str:
    return c.text.upper()


def t_lower(c: Clip) -> str:
    return c.text.lower()


def t_title(c: Clip) -> str:
    # str.title() mangles "don't" into "Don'T"; walk words instead.
    return re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)*",
                  lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), c.text)


def t_sentence(c: Clip) -> str:
    text = c.text.lower()
    return re.sub(r"(^|[.!?]\s+|\n\s*)([^\W\d_])",
                  lambda m: m.group(1) + m.group(2).upper(), text)


def t_unaccent(c: Clip) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", c.text)
                   if unicodedata.category(ch) != "Mn")


def t_slug(c: Clip) -> str:
    text = t_unaccent(Clip(text=c.text)).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def t_snake(c: Clip) -> str:
    return t_slug(c).replace("-", "_")


def t_camel(c: Clip) -> str:
    parts = [p for p in t_slug(c).split("-") if p]
    return parts[0] + "".join(p.capitalize() for p in parts[1:]) if parts else ""


def t_trim(c: Clip) -> str:
    """Strip trailing spaces, collapse runs of blank lines, drop a BOM."""
    text = c.text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in _lines(text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def t_unwrap(c: Clip) -> str:
    """Join hard-wrapped lines back into paragraphs (PDFs, e-mail, man pages)."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", t_trim(c)):
        lines = [ln.strip() for ln in _lines(block) if ln.strip()]
        joined: list[str] = []
        for line in lines:
            if joined and not re.match(r"^([-*+•]|\d+[.)])\s", line) and not joined[-1].endswith("-"):
                joined[-1] += " " + line
            elif joined and joined[-1].endswith("-"):
                joined[-1] = joined[-1][:-1] + line       # de-hyphenate a split word
            else:
                joined.append(line)
        out.append("\n".join(joined))
    return "\n\n".join(out)


def t_single_line(c: Clip) -> str:
    return re.sub(r"\s+", " ", c.text).strip()


def t_quote(c: Clip) -> str:
    return "\n".join(("> " + ln).rstrip() for ln in _lines(t_trim(c)))


def t_bullets(c: Clip) -> str:
    return "\n".join("- " + ln.strip() for ln in _lines(t_trim(c)) if ln.strip())


def t_numbered(c: Clip) -> str:
    lines = [ln.strip() for ln in _lines(t_trim(c)) if ln.strip()]
    return "\n".join(f"{i}. {ln}" for i, ln in enumerate(lines, 1))


def t_code_block(c: Clip) -> str:
    text = t_trim(c)
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}\n{text}\n{fence}"


def t_sort(c: Clip) -> str:
    lines = [ln for ln in _lines(t_trim(c)) if ln.strip()]
    return "\n".join(sorted(lines, key=lambda s: s.strip().lower()))


def t_unique(c: Clip) -> str:
    seen, out = set(), []
    for ln in _lines(t_trim(c)):
        key = ln.strip()
        if key and key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return "\n".join(out)


def t_reverse_lines(c: Clip) -> str:
    return "\n".join(reversed([ln for ln in _lines(t_trim(c))]))


def t_base64(c: Clip) -> str:
    return base64.b64encode(c.text.encode("utf-8")).decode("ascii")


def t_unbase64(c: Clip) -> str:
    raw = re.sub(r"\s+", "", c.text)
    try:
        data = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True)
    except (binascii.Error, ValueError) as e:
        raise TransformError(f"not valid Base64: {e}") from e
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise TransformError("the decoded bytes are not UTF-8 text") from e


def t_urlencode(c: Clip) -> str:
    return urllib.parse.quote(c.text, safe="")


def t_urldecode(c: Clip) -> str:
    return urllib.parse.unquote_plus(c.text)


def t_url_params(c: Clip) -> str:
    """Split a URL into its parts and query string — the debugging paste."""
    u = urllib.parse.urlsplit(c.text.strip())
    if not u.scheme and not u.query:
        raise TransformError("that doesn't look like a URL")
    out = []
    if u.scheme:
        out.append(f"{u.scheme}://{u.netloc}{u.path}")
    for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True):
        out.append(f"  {k} = {v}")
    if u.fragment:
        out.append(f"  #{u.fragment}")
    return "\n".join(out)


def t_sha256(c: Clip) -> str:
    return hashlib.sha256(c.text.encode("utf-8")).hexdigest()


def t_escape_json(c: Clip) -> str:
    return json.dumps(c.text, ensure_ascii=False)


def t_count(c: Clip) -> str:
    text = c.text
    words = len(re.findall(r"\S+", text))
    return (f"{len(text)} characters, {words} words, {len(_lines(text))} lines, "
            f"{len(text.encode('utf-8'))} bytes")


# ---------------------------------------------------------------- catalogue

@dataclass(frozen=True)
class Transform:
    name: str            # stable key, what the CLI takes
    label: str           # what the menu shows
    group: str
    fn: object
    needs_html: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


CATALOGUE: tuple[Transform, ...] = (
    Transform("plain", "Plain text", "Formatting", t_plain, aliases=("text",)),
    Transform("markdown", "Markdown", "Formatting", t_markdown, needs_html=True, aliases=("md",)),
    Transform("unwrap", "Unwrap paragraphs", "Formatting", t_unwrap),
    Transform("trim", "Trim whitespace", "Formatting", t_trim),
    Transform("single-line", "Single line", "Formatting", t_single_line, aliases=("oneline",)),
    Transform("quote", "Markdown quote", "Formatting", t_quote),
    Transform("bullets", "Bullet list", "Formatting", t_bullets),
    Transform("numbered", "Numbered list", "Formatting", t_numbered),
    Transform("code-block", "Fenced code block", "Formatting", t_code_block, aliases=("code",)),

    Transform("json", "JSON, formatted", "Data", t_json),
    Transform("json-min", "JSON, minified", "Data", t_json_min),
    Transform("json-to-csv", "JSON to CSV", "Data", t_json_to_csv),
    Transform("csv-to-table", "CSV to Markdown table", "Data", t_csv_to_table, aliases=("table",)),
    Transform("csv-to-json", "CSV to JSON", "Data", t_csv_to_json),
    Transform("escape-json", "Escape as JSON string", "Data", t_escape_json),

    Transform("upper", "UPPERCASE", "Case", t_upper),
    Transform("lower", "lowercase", "Case", t_lower),
    Transform("title", "Title Case", "Case", t_title),
    Transform("sentence", "Sentence case", "Case", t_sentence),
    Transform("unaccent", "Remove accents", "Case", t_unaccent),
    Transform("slug", "kebab-case slug", "Case", t_slug),
    Transform("snake", "snake_case", "Case", t_snake),
    Transform("camel", "camelCase", "Case", t_camel),

    Transform("sort", "Sort lines", "Lines", t_sort),
    Transform("unique", "Remove duplicate lines", "Lines", t_unique),
    Transform("reverse-lines", "Reverse line order", "Lines", t_reverse_lines),

    Transform("base64", "Base64 encode", "Encoding", t_base64),
    Transform("unbase64", "Base64 decode", "Encoding", t_unbase64),
    Transform("urlencode", "URL encode", "Encoding", t_urlencode),
    Transform("urldecode", "URL decode", "Encoding", t_urldecode),
    Transform("url-params", "Break a URL apart", "Encoding", t_url_params),
    Transform("sha256", "SHA-256", "Encoding", t_sha256),
    Transform("count", "Count characters and words", "Encoding", t_count),
)

BY_NAME: dict[str, Transform] = {}
for _t in CATALOGUE:
    BY_NAME[_t.name] = _t
    for _a in _t.aliases:
        BY_NAME[_a] = _t

GROUPS: tuple[str, ...] = ("Formatting", "Data", "Case", "Lines", "Encoding")


def apply(name: str, clip: Clip) -> str:
    t = BY_NAME.get(name)
    if t is None:
        raise TransformError(f"unknown transform: {name}")
    return t.fn(clip)
