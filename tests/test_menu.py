from oadvpaste.cli import HINTS, build_menu
from oadvpaste.transforms import CATALOGUE


def test_every_row_has_the_three_fields_the_picker_expects():
    """glyph, label, subtext. Two fields and the label is drawn as the icon."""
    rows, _ = build_menu()
    for row in rows:
        assert len(row) == 3
        assert all(isinstance(field, str) for field in row)
        assert row[1] and row[2]                      # a label and a subtext, always


def test_no_field_contains_a_tab():
    """A tab inside a field would split it into another column."""
    rows, _ = build_menu()
    for row in rows:
        for field in row:
            assert "\t" not in field


def test_what_the_picker_returns_maps_back_to_a_transform():
    rows, keys = build_menu()
    for _, label, subtext in rows:
        assert f"{label}\t{subtext}" in keys


def test_every_transform_is_offered_once_plus_the_ai_row():
    rows, keys = build_menu()
    assert len(rows) == len(CATALOGUE) + 1
    assert set(keys.values()) == {t.name for t in CATALOGUE} | {"ai"}


def test_every_transform_has_a_hint_written_for_it():
    for t in CATALOGUE:
        assert t.name in HINTS, f"{t.name} has no hint, the menu would show its name twice"


def test_labels_are_unique_so_a_pick_is_unambiguous():
    rows, _ = build_menu()
    labels = [f"{label}\t{sub}" for _, label, sub in rows]
    assert len(set(labels)) == len(labels)
