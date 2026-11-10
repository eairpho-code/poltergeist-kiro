"""How a human action names the element under the click.

Specification: .kiro/specs/interactive-element/ (Requirement 3)
"""

import pytest

from poltergeist.activity import describe_action


def action(role=None, label=None, **overrides):
    result = {
        "timestamp": "2026-05-15T14:30:41.000Z", "actor": "human", "kind": "click",
        "normalized_x": 110.0, "normalized_y": 105.0, "end_x": None, "end_y": None,
        "ui_element": None if role is None else {"role": role, "label": label},
    }
    result.update(overrides)
    return result


def test_no_element_adds_nothing():
    assert describe_action(action()) == "the human clicked (110.0, 105.0) at 14:30:41 UTC"


def test_a_role_without_a_label_reads_as_before():
    assert describe_action(action("button")) == "the human clicked (110.0, 105.0) on a button at 14:30:41 UTC"


def test_a_role_with_a_label_names_the_label():
    text = describe_action(action("button", "Candle I"))
    assert text == 'the human clicked (110.0, 105.0) on a button "Candle I" at 14:30:41 UTC'


def test_a_text_with_a_label_is_the_text_not_a_text():
    text = describe_action(action("text", "2 of 3 candles lit"))
    assert text == 'the human clicked (110.0, 105.0) on the text "2 of 3 candles lit" at 14:30:41 UTC'
    assert "on a text" not in text


def test_a_text_without_a_label_is_some_text():
    text = describe_action(action("text"))
    assert text == "the human clicked (110.0, 105.0) on some text at 14:30:41 UTC"
    assert "on a text" not in text


@pytest.mark.parametrize("role", ["switch", "text_field", "link", "image"])
def test_other_roles_follow_the_same_pattern(role):
    assert f'on a {role} "Go"' in describe_action(action(role, "Go"))
    assert f"on a {role} at" in describe_action(action(role))


def test_a_drag_names_the_element_in_the_same_way():
    text = describe_action(action("button", "Candle I", kind="drag", end_x=10.0, end_y=20.0))
    assert text == 'the human dragged from (110.0, 105.0) to (10.0, 20.0) on a button "Candle I" at 14:30:41 UTC'


def test_an_empty_label_counts_as_no_label():
    assert "on a button at" in describe_action(action("button", ""))
    assert "on some text at" in describe_action(action("text", ""))


def test_a_missing_ui_element_key_is_fine():
    bare = action()
    del bare["ui_element"]
    assert describe_action(bare) == "the human clicked (110.0, 105.0) at 14:30:41 UTC"
