from tavern.knowledge import ground
from tavern.strategy import parse_plan
from tavern.summarizer import summarize_outcome

STATE_T1 = {
    "game_time": "01:00",
    "players": {
        "3": {"name": "Dakkar", "race": "Orc", "team": "ally", "food": "6/10"},
        "5": {"name": "Vex", "race": "Undead", "team": "enemy", "food": "7/10"},
    },
}
STATE_T2 = {
    "game_time": "04:00",
    "players": {
        "3": {"name": "Dakkar", "race": "Orc", "team": "ally", "food": "14/20"},
        "5": {"name": "Vex", "race": "Undead", "team": "enemy", "food": "10/16"},
    },
    "events": ["Dakkar's Blademaster reached level 2", "a hero died near mid"],
}


def test_grounding_tailored_to_races_in_play():
    g = ground(STATE_T1, "ally")
    assert "YOU  Orc" in g          # our race tip
    assert "ENEMY Undead" in g      # enemy race tip
    assert "Timing windows" in g


def test_outcome_first_plan_has_no_prior():
    assert "first plan" in summarize_outcome(None, STATE_T1, "ally")


def test_outcome_reports_army_trend_and_events():
    out = summarize_outcome(STATE_T1, STATE_T2, "ally")
    assert "grew" in out and "6→14" in out
    assert "hero died" in out


def test_plan_intent_is_normalized_on_parse():
    # free-form intent from the model gets mapped to controlled vocab
    gp = parse_plan('{"intent": "defend our gold mine", "objective": "hold east", "posture": 0.6}')
    assert gp.intent == "defend"
    # falls back to objective text when intent missing
    gp2 = parse_plan('{"objective": "take a fast expansion", "posture": 0.3}')
    assert gp2.intent == "expand_now"
