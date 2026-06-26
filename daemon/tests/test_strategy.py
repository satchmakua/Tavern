import asyncio

import pytest

from tavern.llm import FakeLLM
from tavern.schema import OutputParseError
from tavern.strategy import (
    STRATEGIST_MARKER,
    GamePlan,
    Strategist,
    build_strategist_prompt,
    parse_plan,
)
from tavern.summarizer import summarize_team

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


def test_plan_parses_and_clamps():
    gp = parse_plan('{"phase":"mid","objective":"pressure natural","posture":4.0,"target_player":"Vex"}')
    assert gp.phase == "mid"
    assert gp.posture == 1.0  # clamped
    assert gp.target_player == "Vex"
    assert "pressure natural" in gp.headline()


def test_plan_blank_to_none():
    gp = parse_plan('{"objective":"  ","tech_goal":""}')
    assert gp.objective is None and gp.tech_goal is None


def test_plan_invalid_raises():
    with pytest.raises(OutputParseError):
        parse_plan("not json")


def test_summarize_team_groups_both_sides():
    s = summarize_team(STATE, "ally")
    assert "Your team (ally):" in s
    assert "Dakkar (Orc)" in s
    assert "Enemy team:" in s and "Vex (Undead)" in s


def test_strategist_prompt_has_marker():
    prompt = build_strategist_prompt("summary", [{"speaker": "you", "text": "all in"}], None)
    assert STRATEGIST_MARKER in prompt
    assert "all in" in prompt


@pytest.mark.asyncio
async def test_fake_llm_returns_a_plan_for_strategist_calls():
    llm = FakeLLM(seed=1)
    strat = Strategist("ally", llm, "fake")
    plan = await strat.propose(summarize_team(STATE, "ally"), [])
    assert isinstance(plan, GamePlan)
    assert plan.phase in {"opening", "early", "mid", "late"}
    assert strat.plan is plan  # remembered for next revision
