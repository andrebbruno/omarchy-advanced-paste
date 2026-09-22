import pytest

from oadvpaste.transforms import BY_NAME, CATALOGUE, Clip, TransformError, apply


def t(name, text="", html=None):
    return apply(name, Clip(text=text, html=html))


# ---------------------------------------------------------------- formatting

def test_plain_strips_html_when_the_clipboard_is_rich():
    html = "<p>Hello <b>world</b></p><p>Second</p>"
    assert t("plain", "Hello world\nSecond", html) == "Hello world\n\nSecond"


def test_plain_keeps_text_when_there_is_no_rich_flavour():
    assert t("plain", "  already plain  ") == "already plain"


def test_unwrap_joins_hard_wrapped_lines():
    text = "The quick brown\nfox jumps over\nthe lazy dog.\n\nSecond paragraph\nhere."
    assert t("unwrap", text) == "The quick brown fox jumps over the lazy dog.\n\nSecond paragraph here."


def test_unwrap_keeps_list_items_apart():
    assert t("unwrap", "- one\n- two\n- three") == "- one\n- two\n- three"


def test_unwrap_rejoins_a_hyphen_split_word():
    assert t("unwrap", "inter-\nnational") == "international"


def test_trim_collapses_blank_lines_and_trailing_space():
    assert t("trim", "a   \n\n\n\nb\r\n") == "a\n\nb"


def test_trim_drops_a_bom():
    assert t("trim", "﻿hello") == "hello"


def test_single_line():
    assert t("single-line", "a\n  b\t c ") == "a b c"


def test_quote_and_bullets_and_numbered():
    assert t("quote", "a\nb") == "> a\n> b"
    assert t("bullets", "a\n\nb") == "- a\n- b"
    assert t("numbered", "a\nb") == "1. a\n2. b"


def test_code_block_grows_the_fence_when_the_text_has_one():
    assert t("code-block", "x = 1") == "```\nx = 1\n```"
    out = t("code-block", "```\nnested\n```")
    assert out.startswith("````\n") and out.endswith("\n````")


# ---------------------------------------------------------------- data

def test_json_pretty_prints():
    assert t("json", '{"b":1,"a":[2,3]}') == '{\n  "b": 1,\n  "a": [\n    2,\n    3\n  ]\n}'


def test_json_accepts_python_literals():
    assert t("json", "{'a': None, 'b': True}") == '{\n  "a": null,\n  "b": true\n}'


def test_json_keeps_accents_readable():
    assert t("json", '{"nome":"Ação"}') == '{\n  "nome": "Ação"\n}'


def test_json_min():
    assert t("json-min", '{ "a" : [1, 2] }') == '{"a":[1,2]}'


def test_json_reports_bad_input_instead_of_crashing():
    with pytest.raises(TransformError):
        t("json", "not json at all {")


def test_json_to_csv_unions_the_keys():
    out = t("json-to-csv", '[{"a":1,"b":2},{"a":3,"c":4}]')
    assert out == "a,b,c\n1,2,\n3,,4"


def test_json_to_csv_rejects_a_bare_array():
    with pytest.raises(TransformError):
        t("json-to-csv", "[1,2,3]")


def test_csv_to_table():
    out = t("csv-to-table", "name,qty\nApple,3\nPear,5")
    assert out == ("| name | qty |\n| --- | --- |\n| Apple | 3 |\n| Pear | 5 |")


def test_csv_to_table_handles_a_spreadsheet_tsv_selection():
    out = t("csv-to-table", "name\tqty\nApple\t3")
    assert out.splitlines()[0] == "| name | qty |"


def test_csv_to_table_escapes_a_pipe():
    assert "a\\|b" in t("csv-to-table", "col\na|b")


def test_csv_to_json():
    assert t("csv-to-json", "a,b\n1,2") == '[\n  {\n    "a": "1",\n    "b": "2"\n  }\n]'


def test_escape_json():
    assert t("escape-json", 'he said "hi"\n') == '"he said \\"hi\\"\\n"'


# ---------------------------------------------------------------- case

def test_title_case_does_not_mangle_apostrophes():
    assert t("title", "don't stop believing") == "Don't Stop Believing"


def test_title_case_keeps_accented_letters():
    assert t("title", "ação e reação") == "Ação E Reação"


def test_sentence_case():
    assert t("sentence", "HELLO there. SECOND one!") == "Hello there. Second one!"


def test_unaccent():
    assert t("unaccent", "ação não é fácil") == "acao nao e facil"


def test_slug_snake_camel():
    assert t("slug", "Relatório Final 2026!") == "relatorio-final-2026"
    assert t("snake", "Relatório Final") == "relatorio_final"
    assert t("camel", "relatório final agora") == "relatorioFinalAgora"


def test_camel_on_empty_text():
    assert t("camel", "!!!") == ""


# ---------------------------------------------------------------- lines

def test_sort_is_case_insensitive():
    assert t("sort", "banana\nApple\ncherry") == "Apple\nbanana\ncherry"


def test_unique_keeps_the_first_occurrence():
    assert t("unique", "a\nb\na\nc\nb") == "a\nb\nc"


def test_reverse_lines():
    assert t("reverse-lines", "1\n2\n3") == "3\n2\n1"


# ---------------------------------------------------------------- encoding

def test_base64_round_trip():
    assert t("unbase64", t("base64", "ação — ok")) == "ação — ok"


def test_unbase64_tolerates_missing_padding_and_newlines():
    assert t("unbase64", "aGVsbG8\n") == "hello"


def test_unbase64_reports_garbage():
    with pytest.raises(TransformError):
        t("unbase64", "!!!not base64!!!")


def test_unbase64_reports_non_utf8_bytes():
    with pytest.raises(TransformError):
        t("unbase64", "/w==")            # 0xFF is not valid UTF-8


def test_url_encode_decode():
    assert t("urlencode", "a b/c?d=e") == "a%20b%2Fc%3Fd%3De"
    assert t("urldecode", "a%20b+c") == "a b c"


def test_url_params_breaks_a_query_string_apart():
    out = t("url-params", "https://x.dev/path?a=1&b=two%20words#frag")
    assert out == "https://x.dev/path\n  a = 1\n  b = two words\n  #frag"


def test_url_params_refuses_plain_text():
    with pytest.raises(TransformError):
        t("url-params", "just some words")


def test_sha256():
    assert t("sha256", "abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_count():
    assert t("count", "ação sim\nnão") == "12 characters, 3 words, 2 lines, 15 bytes"


# ---------------------------------------------------------------- catalogue

def test_every_transform_survives_empty_text():
    """A transform may refuse the input, but it may never blow up with a traceback."""
    for entry in CATALOGUE:
        try:
            entry.fn(Clip(text="", html=None))
        except TransformError:
            pass


def test_every_transform_survives_junk():
    junk = "\x00﻿ ação\n\n\t<b>x</b> {not: json} ###\n"
    for entry in CATALOGUE:
        try:
            entry.fn(Clip(text=junk, html="<p>ação <b>x</b></p>"))
        except TransformError:
            pass


def test_names_and_aliases_are_unique():
    seen = set()
    for entry in CATALOGUE:
        for key in (entry.name, *entry.aliases):
            assert key not in seen, f"duplicate key {key}"
            seen.add(key)
    assert len(BY_NAME) == len(seen)


def test_unknown_transform_is_reported():
    with pytest.raises(TransformError):
        t("does-not-exist", "x")
