"""Strategy track S1 — the deliberate per-team planner ("coach").

The per-persona loop is fast and chatty; it's good at banter but bad at strategy
(an 8B asked to trash-talk and strategize in one cheap call defaults to vibes —
e.g. `aggression=1.0` every turn). The Strategist splits the macro brain out:

  - one Strategist per team, holding a persistent `GamePlan`;
  - it runs on a slow cadence (and on big events), reading fuller team-scoped
    state, the humans' calls, and its own previous plan, then revises with
    explicit reasoning;
  - personas derive their chat + directives *from* the team plan instead of
    reinventing strategy each tick.

S1 keeps everything on the local 8B and verifiable against FakeState. Grounding,
outcome-feedback, and a constrained directive vocabulary land in S2.
"""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .directives import normalize_intent
from .llm import LLM
from .schema import OutputParseError, _extract_json

# Controlled intents a plan can lean on (design §4). Normalized in S2 via directives.py.
STRATEGY_VOCAB = ("expand_now", "tech_up", "mass_<unit>", "attack_<player>", "defend", "creep_more")

# A marker the FakeLLM uses to tell strategist calls apart from persona calls.
STRATEGIST_MARKER = "[STRATEGIST]"

STRATEGIST_SYSTEM = (
    "You are the strategic coordinator (\"coach\") for the {team} team in a Warcraft 3 "
    "melee game. You do NOT chat or trash-talk — you set the team's game plan. You are given "
    "RTS notes, the game state, what your human teammates asked for, the enemy's play, and the "
    "outcome of your previous plan. Use them — adapt when the board changed, hold steady when it "
    "didn't (don't thrash). Give one short sentence of reasoning grounded in the state.\n"
    "Set `intent` to exactly ONE controlled value: expand_now, tech_up, defend, creep_more, "
    "mass_<unit> (e.g. mass_grunt), or attack_<player>. Set `objective` to a plain-language "
    "explanation, and `posture` 0..1 (0 = turtle, 1 = all-in) reflecting the actual board, not mood."
)


class GamePlan(BaseModel):
    """A team's current strategic plan. Held by the Strategist, read by personas."""

    model_config = ConfigDict(extra="ignore")

    phase: Optional[str] = None          # opening | early | mid | late
    intent: Optional[str] = None         # controlled vocab (normalized in S2); None if unmapped
    objective: Optional[str] = None      # the primary objective, plain language
    target_player: Optional[str] = None  # who to focus
    posture: Optional[float] = None      # 0..1 team aggression baseline
    tech_goal: Optional[str] = None      # e.g. tier2, air, casters
    rationale: Optional[str] = None      # one short sentence (logged / shown dim)

    @field_validator("posture")
    @classmethod
    def _clamp(cls, v: Optional[float]) -> Optional[float]:
        return None if v is None else max(0.0, min(1.0, float(v)))

    @field_validator("phase", "intent", "objective", "target_player", "tech_goal", "rationale")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    def headline(self) -> str:
        bits = []
        if self.phase:
            bits.append(self.phase)
        if self.intent:
            bits.append(self.intent)
        if self.objective:
            bits.append(self.objective)
        if self.target_player:
            bits.append(f"target {self.target_player}")
        if self.posture is not None:
            bits.append(f"posture {self.posture}")
        if self.tech_goal:
            bits.append(f"tech {self.tech_goal}")
        return " | ".join(bits) if bits else "(no plan yet)"

    def as_prompt_block(self) -> str:
        """How a persona sees the team plan in its prompt."""
        return self.headline()


def parse_plan(raw: str) -> GamePlan:
    snippet = _extract_json(raw)
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as e:
        raise OutputParseError(f"plan not valid JSON: {e}; raw={raw!r}") from e
    if not isinstance(data, dict):
        raise OutputParseError(f"plan expected an object, got {type(data).__name__}: {raw!r}")
    try:
        plan = GamePlan.model_validate(data)
    except Exception as e:
        raise OutputParseError(f"plan schema validation failed: {e}; raw={raw!r}") from e
    # S2: normalize the intent to the controlled vocabulary (fall back to objective text).
    canon, _ = normalize_intent(plan.intent or plan.objective)
    plan.intent = canon  # None when nothing maps — surfaced, not invented
    return plan


def build_strategist_prompt(
    team_summary: str,
    chat_history: list[dict],
    prev_plan: Optional[GamePlan],
    last_outcome: Optional[str] = None,
    grounding: Optional[str] = None,
) -> str:
    parts = [STRATEGIST_MARKER]
    if grounding:
        parts += ["[RTS NOTES]", grounding, ""]
    parts += ["[TEAM STATE]", team_summary, "", "[RECENT CHAT]"]
    if chat_history:
        parts += [f"{l['speaker']}: {l['text']}" for l in chat_history]
    else:
        parts.append("(quiet so far)")
    parts += ["", "[PREVIOUS PLAN]", prev_plan.headline() if prev_plan else "none"]
    parts += ["", "[OUTCOME SINCE LAST PLAN]", last_outcome or "first plan; no prior outcome yet."]
    parts += [
        "",
        'Respond with one JSON object: {"phase": str|null, "intent": str|null, '
        '"objective": str|null, "target_player": str|null, "posture": number|null, '
        '"tech_goal": str|null, "rationale": str|null}. `intent` must be one of '
        "expand_now/tech_up/defend/creep_more/mass_<unit>/attack_<player>. "
        "Be decisive; revise only if the board actually changed.",
    ]
    return "\n".join(parts)


class Strategist:
    """One per team. Owns the team's GamePlan and proposes revisions."""

    def __init__(self, team: str, llm: LLM, model: str) -> None:
        self.team = team
        self._llm = llm
        self._model = model
        self.plan: Optional[GamePlan] = None
        self.system_prompt = STRATEGIST_SYSTEM.format(team=team)

    async def propose(
        self,
        team_summary: str,
        chat_history: list[dict],
        last_outcome: Optional[str] = None,
        grounding: Optional[str] = None,
    ) -> GamePlan:
        user = build_strategist_prompt(
            team_summary, chat_history, self.plan, last_outcome, grounding
        )
        raw = await self._llm.complete(model=self._model, system=self.system_prompt, user=user)
        plan = parse_plan(raw)
        self.plan = plan
        return plan
