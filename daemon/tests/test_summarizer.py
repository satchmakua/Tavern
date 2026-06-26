from tavern.summarizer import build_user_prompt, summarize

STATE = {
    "game_time": "03:10",
    "map": "(4) Lost Temple",
    "players": {
        "1": {"name": "you", "race": "Human", "team": "ally", "gold": 600},
        "3": {"name": "Dakkar", "race": "Orc", "team": "ally", "army": ["6 grunts"]},
        "5": {"name": "Vex", "race": "Undead", "team": "enemy", "heroes": ["Death Knight L3"]},
    },
    "events": ["enemy expanding east"],
}


def test_empty_state():
    assert "lobby" in summarize({}, 3).lower()


def test_scoped_from_dakkar_perspective():
    s = summarize(STATE, 3)
    assert "You: Dakkar" in s
    # player 1 is Dakkar's ally, Vex is the enemy
    assert "Allies:" in s and "you (Human)" in s
    assert "Enemies:" in s and "Vex (Undead)" in s
    assert "enemy expanding east" in s


def test_scoped_from_enemy_perspective_flips_sides():
    s = summarize(STATE, 5)  # Vex
    assert "You: Vex" in s
    # from Vex's side, you + Dakkar are enemies
    assert "Enemies:" in s and "Dakkar (Orc)" in s


def test_build_user_prompt_includes_chat_and_schema_hint():
    prompt = build_user_prompt("summary here", [{"speaker": "you", "text": "push"}])
    assert "summary here" in prompt
    assert "you: push" in prompt
    assert "say_in_chat" in prompt  # schema reminder present
