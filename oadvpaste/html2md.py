"""HTML -> Markdown, standard library only.

The clipboard's text/html flavour is what a browser or word processor leaves behind
when you copy rich text. Turning it into Markdown is the transform people reach for
most, and pulling in pandoc or html2text for it would make the package heavier than
everything else it does put together.

Only the subset that survives a copy is handled: headings, emphasis, links, images,
lists, code, quotes, rules and simple tables. Anything else degrades to its text.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# Blocks that start on their own line; anything else is inline.
BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote",
         "pre", "hr", "table", "tr", "section", "article", "header", "footer", "main"}
SKIP = {"script", "style", "head", "meta", "title", "noscript", "svg"}
# Void elements never close, so they must not open a skipped region: Chrome prefixes
# every rich copy with <meta charset='utf-8'>, and counting that as "skip from here"
# swallows the whole document.
VOID = {"meta", "link", "base", "br", "img", "hr", "input", "source", "col", "area"}
INLINE_MARK = {"strong": "**", "b": "**", "em": "*", "i": "*", "u": "_", "del": "~~",
               "s": "~~", "strike": "~~", "code": "`", "mark": "=="}




def _clean_ws(text: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", text)


class _Converter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf = ""
        self.skip_depth = 0
        self.pre_depth = 0
        self.list_stack: list[dict] = []      # {"ordered": bool, "index": int}
        self.quote_depth = 0
        self.link: str | None = None
        self.link_text: list[str] = []
        self.cell: list[str] | None = None    # current table cell buffer
        self.row: list[str] | None = None
        self.table: list[list[str]] | None = None
        self.table_head = False

    # ------------------------------------------------------------------ helpers
    def _emit(self, text: str):
        if self.cell is not None:
            self.cell.append(text)
        elif self.link is not None:
            self.link_text.append(text)
        else:
            self.buf += text

    def _newline(self, count: int = 1):
        """End the current line, leaving exactly `count` newlines — never a stack of them.

        Nothing to separate yet (the document has only opened tags so far) means
        nothing to do, which is what keeps a leading blank line out of the result.
        """
        if self.cell is not None or self.link is not None:
            return
        # A quote prefix nothing was written after is punctuation, not content.
        self.buf = re.sub(r"(?:> )+$", "", self.buf)
        if not self.buf.strip():
            return
        trailing = len(self.buf) - len(self.buf.rstrip("\n"))
        self.buf += "\n" * max(0, count - trailing)

    def _prefix(self) -> str:
        return "> " * self.quote_depth

    # ------------------------------------------------------------------ tags
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            if tag not in VOID:
                self.skip_depth += 1
            return
        if self.skip_depth:
            return

        if tag == "br":
            self._emit("  \n" + self._prefix())
        elif tag in ("p", "div", "section", "article"):
            self._newline(2)
            self._emit(self._prefix())
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline(2)
            self._emit(self._prefix() + "#" * int(tag[1]) + " ")
        elif tag == "hr":
            self._newline(2)
            self._emit(self._prefix() + "---")
            self._newline(2)
        elif tag in ("ul", "ol"):
            if not self.list_stack:
                self._newline(2)
            self.list_stack.append({"ordered": tag == "ol", "index": 0})
        elif tag == "li":
            self._newline(1)
            depth = max(0, len(self.list_stack) - 1)
            item = self.list_stack[-1] if self.list_stack else {"ordered": False, "index": 0}
            item["index"] += 1
            marker = f"{item['index']}. " if item["ordered"] else "- "
            self._emit(self._prefix() + "  " * depth + marker)
        elif tag == "blockquote":
            self._newline(2)
            self.quote_depth += 1
            self._emit(self._prefix())
        elif tag == "pre":
            self._newline(2)
            self.pre_depth += 1
            self._emit("```\n")
        elif tag == "code" and self.pre_depth:
            pass                                    # already inside a fence
        elif tag in INLINE_MARK:
            self._emit(INLINE_MARK[tag])
        elif tag == "a":
            self.link = a.get("href", "")
            self.link_text = []
        elif tag == "img":
            alt, src = a.get("alt", ""), a.get("src", "")
            if src:
                self._emit(f"![{alt}]({src})")
        elif tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
            if tag == "th":
                self.table_head = True

    def handle_endtag(self, tag):
        if tag in SKIP:
            if tag not in VOID:
                self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return

        if tag in ("p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline(2)
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            if not self.list_stack:
                self._newline(2)
        elif tag == "blockquote":
            self.quote_depth = max(0, self.quote_depth - 1)
            self._newline(2)
        elif tag == "pre":
            self.pre_depth = max(0, self.pre_depth - 1)
            if self.buf and not self.buf.endswith("\n"):
                self._emit("\n")
            self._emit("```")
            self._newline(2)
        elif tag == "code" and self.pre_depth:
            pass
        elif tag in INLINE_MARK:
            self._emit(INLINE_MARK[tag])
        elif tag == "a" and self.link is not None:
            text = "".join(self.link_text).strip()
            href, self.link, self.link_text = self.link, None, []
            if not href or href.startswith("javascript:"):
                self._emit(text)
            elif text == href or not text:
                self._emit(f"<{href}>")
            else:
                self._emit(f"[{text}]({href})")
        elif tag in ("td", "th") and self.cell is not None:
            value = _clean_ws("".join(self.cell)).strip().replace("|", "\\|")
            if self.row is not None:
                self.row.append(value)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self._flush_table()

    def _flush_table(self):
        rows = [r for r in (self.table or []) if r]
        self.table = None
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        self._newline(2)
        head = rows[0] if self.table_head or len(rows) > 1 else [""] * width
        body = rows[1:] if head is rows[0] else rows
        self._emit("| " + " | ".join(head) + " |\n")
        self._emit("| " + " | ".join("---" for _ in range(width)) + " |\n")
        for r in body:
            self._emit("| " + " | ".join(r) + " |\n")
        self.table_head = False
        self._newline(2)

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.pre_depth:
            self._emit(data)
            return
        text = _clean_ws(data)
        if not text.strip():
            # A newline between two block tags is layout, not content; a space between
            # two inline runs ("</b> and <i>") is content and has to survive.
            tail = self.cell[-1] if self.cell else (self.link_text[-1] if self.link_text else self.buf)
            if text == " " and tail and not tail.endswith((" ", "\n")):
                self._emit(" ")
            return
        self._emit(text)


def html_to_markdown(html: str) -> str:
    c = _Converter()
    c.feed(html)
    c.close()
    if c.table is not None:
        c._flush_table()
    text = c.buf
    # Trailing whitespace goes, except the two spaces that *are* a Markdown hard break.
    text = re.sub(r"[ \t]+\n", lambda m: "  \n" if m.group(0) == "  \n" else "\n", text)
    text = re.sub(r"\n(?:> )+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_tags(html: str) -> str:
    """Plain text out of HTML: what "paste as plain text" should leave behind."""
    parts: list[str] = []

    class _Plain(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in SKIP:
                if tag not in VOID:
                    self.skip += 1
            elif tag == "br" or tag in BLOCK:
                parts.append("\n")

        def handle_endtag(self, tag):
            if tag in SKIP:
                if tag not in VOID:
                    self.skip = max(0, self.skip - 1)
            elif tag in BLOCK:
                parts.append("\n")

        def handle_data(self, data):
            if not self.skip:
                parts.append(data)

    p = _Plain()
    p.feed(html)
    p.close()
    text = "".join(parts)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
