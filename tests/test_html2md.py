from oadvpaste.html2md import html_to_markdown, strip_tags
from oadvpaste.transforms import Clip, apply


def md(html: str) -> str:
    return html_to_markdown(html)


def test_headings_and_paragraphs():
    assert md("<h1>Title</h1><p>Body text</p>") == "# Title\n\nBody text"


def test_emphasis():
    assert md("<p>a <b>bold</b> and <i>italic</i></p>") == "a **bold** and *italic*"


def test_link():
    assert md('<p>see <a href="https://x.dev">the site</a></p>') == "see [the site](https://x.dev)"


def test_bare_link_becomes_an_autolink():
    assert md('<a href="https://x.dev">https://x.dev</a>') == "<https://x.dev>"


def test_javascript_href_is_dropped():
    assert md('<a href="javascript:alert(1)">click</a>') == "click"


def test_image():
    assert md('<img src="/a.png" alt="A cat">') == "![A cat](/a.png)"


def test_unordered_list():
    assert md("<ul><li>one</li><li>two</li></ul>") == "- one\n- two"


def test_ordered_list_numbers_itself():
    assert md("<ol><li>one</li><li>two</li><li>three</li></ol>") == "1. one\n2. two\n3. three"


def test_nested_list_is_indented():
    out = md("<ul><li>one<ul><li>deeper</li></ul></li></ul>")
    assert out == "- one\n  - deeper"


def test_blockquote():
    assert md("<blockquote><p>quoted</p></blockquote>").startswith("> ")


def test_pre_becomes_a_fence():
    assert md("<pre><code>x = 1\ny = 2</code></pre>") == "```\nx = 1\ny = 2\n```"


def test_inline_code():
    assert md("<p>run <code>ls -la</code> now</p>") == "run `ls -la` now"


def test_horizontal_rule():
    assert "---" in md("<p>a</p><hr><p>b</p>")


def test_table():
    out = md("<table><tr><th>name</th><th>qty</th></tr><tr><td>Apple</td><td>3</td></tr></table>")
    assert out == "| name | qty |\n| --- | --- |\n| Apple | 3 |"


def test_script_and_style_are_dropped():
    assert md("<p>keep</p><script>alert(1)</script><style>p{}</style>") == "keep"


def test_entities_are_decoded():
    assert md("<p>caf&eacute; &amp; ch&#225;</p>") == "café & chá"


def test_br_becomes_a_hard_break():
    assert md("<p>one<br>two</p>") == "one  \ntwo"


def test_blank_lines_never_stack_up():
    out = md("<div><p>a</p></div><div><p>b</p></div>")
    assert "\n\n\n" not in out


def test_real_world_copy_from_a_browser():
    html = """<meta charset='utf-8'><div style="color:#000"><h2>Release notes</h2>
    <p>Version <strong>1.2</strong> fixes <a href="https://github.com/x/y/issues/3">issue&nbsp;3</a>.</p>
    <ul><li>Faster startup</li><li>Fewer crashes</li></ul></div>"""
    out = md(html)
    assert out.startswith("## Release notes")
    assert "**1.2**" in out
    assert "[issue 3](https://github.com/x/y/issues/3)" in out
    assert "- Faster startup\n- Fewer crashes" in out


def test_strip_tags_keeps_paragraphs_apart():
    # Plain text should still read like the page did: a blank line between blocks,
    # a single newline inside one.
    assert strip_tags("<h1>Title</h1><p>a</p><p>b</p>") == "Title\n\na\n\nb"
    assert strip_tags("<p>one<br>two</p>") == "one\ntwo"


def test_markdown_transform_falls_back_to_html_in_the_text_flavour():
    assert apply("markdown", Clip(text="<h1>Hi</h1>")) == "# Hi"


def test_markdown_transform_refuses_plain_prose():
    import pytest
    from oadvpaste.transforms import TransformError
    with pytest.raises(TransformError):
        apply("markdown", Clip(text="just words, nothing rich"))
