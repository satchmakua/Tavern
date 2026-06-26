import pytest

from tavern.schema import OutputParseError, PersonaOutput, parse_output


def test_parse_basic():
    out = parse_output('{"say_in_chat": "rax done", "say_aloud": null, '
                        '"directive": {"strategy": "expand_now", "aggression": 0.3}, '
                        '"thinking": "hold"}')
    assert out.say_in_chat == "rax done"
    assert out.say_aloud is None
    assert out.directive is not None
    assert out.directive.strategy == "expand_now"
    assert out.directive.aggression == 0.3
    assert not out.is_silent()


def test_parse_tolerates_code_fence_and_prose():
    raw = "Sure!\n```json\n{\"say_in_chat\": \"gg\"}\n```\nhope that helps"
    out = parse_output(raw)
    assert out.say_in_chat == "gg"


def test_aggression_is_clamped():
    out = parse_output('{"directive": {"aggression": 5}}')
    assert out.directive.aggression == 1.0
    out2 = parse_output('{"directive": {"aggression": -2}}')
    assert out2.directive.aggression == 0.0


def test_blank_strings_become_none_and_silent():
    out = parse_output('{"say_in_chat": "   ", "say_aloud": ""}')
    assert out.say_in_chat is None
    assert out.say_aloud is None
    assert out.is_silent()


def test_empty_directive_dropped():
    out = parse_output('{"say_in_chat": "hi", "directive": {"strategy": null, "aggression": null}}')
    assert out.directive is None


def test_extra_keys_ignored():
    out = parse_output('{"say_in_chat": "hi", "mood": "angry"}')
    assert out.say_in_chat == "hi"


def test_invalid_json_raises():
    with pytest.raises(OutputParseError):
        parse_output("not json at all")


def test_non_object_raises():
    with pytest.raises(OutputParseError):
        parse_output("[1, 2, 3]")
