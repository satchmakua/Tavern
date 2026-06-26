"""Strategy track S2 — grounding. Compact RTS knowledge fed to the Strategist so
its plans rest on real heuristics (build orders, timings, matchup principles)
rather than vibes. Kept terse on purpose: it goes in every strategist prompt.

This is the lightweight, in-prompt form. Heavier retrieval (RAG over pro replays
/ guides) is a later upgrade; the interface here (`ground(state, team)`) stays the
same.
"""
from __future__ import annotations

from typing import Any

_RACE_TIPS = {
    "orc": "Orc — blademaster harass into raiders; grunts core; burrows for defense; bloodlust/shaman spike; strong mid-game timing push.",
    "human": "Human — footmen+rifle; militia fast-expand; tech to sorceress/priest; towers + AM blink for defense; MK for early creeping.",
    "undead": "Undead — ghoul economy + very fast expand; fiends vs ranged/air; DK coil/nova + lich; statues to sustain; punish greedy openings.",
    "night elf": "Night Elf — archers/huntresses; ancient mobility; wisp detonate vs casters; keeper/BM tier-1 creep heavy; hunt's hall timing.",
}
_RACE_TIPS["nightelf"] = _RACE_TIPS["night elf"]
_RACE_TIPS["elf"] = _RACE_TIPS["night elf"]

_TIMINGS = (
    "Timing windows: pre-3:00 scout + creep; ~3–6:00 first hero power spike and first expansion decision; "
    "~6–10:00 tier-2 timing pushes punish a greedy expand; late game tech/upkeep favors whoever held more bases."
)


def _races_on(state: dict[str, Any], team: str, *, ours: bool) -> list[str]:
    players = (state or {}).get("players", {}) or {}
    out = []
    for p in players.values():
        on_team = p.get("team", "ally") == team
        if on_team == ours:
            r = str(p.get("race", "")).strip().lower()
            if r and r not in out:
                out.append(r)
    return out


def ground(state: dict[str, Any], team: str) -> str:
    """Return a short knowledge block tailored to the races actually in play."""
    if not state:
        return _TIMINGS
    lines: list[str] = []
    for r in _races_on(state, team, ours=True):
        tip = _RACE_TIPS.get(r)
        if tip:
            lines.append("YOU  " + tip)
    for r in _races_on(state, team, ours=False):
        tip = _RACE_TIPS.get(r)
        if tip:
            lines.append("ENEMY " + tip)
    lines.append(_TIMINGS)
    return "\n".join(lines)
