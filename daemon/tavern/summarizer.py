"""Reduce a raw game-state snapshot to ~15-20 lines of natural language, scoped
to one player's perspective, before it's fed to the LLM (design §9).

Feeding raw state every tick burns context and confuses the model. The snapshot
shape is whatever the Bridge writes; this summarizer is tolerant of missing keys
so it also works against the FakeState scenarios.
"""
from __future__ import annotations

from typing import Any


def _fmt_player(pid: str, p: dict[str, Any]) -> str:
    bits = []
    if "food" in p:
        bits.append(f"food {p['food']}")
    if "gold" in p:
        bits.append(f"{p['gold']}g")
    if "lumber" in p:
        bits.append(f"{p['lumber']}w")
    army = p.get("army")
    if army:
        bits.append("army: " + ", ".join(army) if isinstance(army, list) else f"army: {army}")
    heroes = p.get("heroes")
    if heroes:
        bits.append("heroes: " + ", ".join(heroes) if isinstance(heroes, list) else f"heroes: {heroes}")
    tail = (" — " + "; ".join(bits)) if bits else ""
    return f"{p.get('name', 'P' + pid)} ({p.get('race', '?')}){tail}"


def summarize(state: dict[str, Any], player_id: int) -> str:
    """Return a compact, player-scoped natural-language summary of `state`."""
    if not state:
        return "No game state yet — you're in the lobby / opening seconds."

    players: dict[str, Any] = state.get("players", {}) or {}
    me = players.get(str(player_id))
    my_team = (me or {}).get("team", "ally")

    lines: list[str] = []
    header = []
    if state.get("game_time"):
        header.append(f"time {state['game_time']}")
    if state.get("map"):
        header.append(f"map {state['map']}")
    if header:
        lines.append("Game: " + ", ".join(header))

    if me:
        lines.append("You: " + _fmt_player(str(player_id), me))

    allies = [
        (pid, p) for pid, p in players.items()
        if pid != str(player_id) and p.get("team", "ally") == my_team
    ]
    enemies = [(pid, p) for pid, p in players.items() if p.get("team", "ally") != my_team]

    if allies:
        lines.append("Allies:")
        lines.extend("  - " + _fmt_player(pid, p) for pid, p in allies)
    if enemies:
        lines.append("Enemies:")
        lines.extend("  - " + _fmt_player(pid, p) for pid, p in enemies)

    events = state.get("events") or []
    if events:
        lines.append("Recent events:")
        lines.extend(f"  - {e}" for e in events[-5:])

    return "\n".join(lines)


def summarize_team(state: dict[str, Any], team: str) -> str:
    """A fuller, team-scoped summary for the Strategist (both sides, all members)."""
    if not state:
        return "No game state yet — lobby / opening seconds."

    players: dict[str, Any] = state.get("players", {}) or {}
    lines: list[str] = []
    header = []
    if state.get("game_time"):
        header.append(f"time {state['game_time']}")
    if state.get("map"):
        header.append(f"map {state['map']}")
    if header:
        lines.append("Game: " + ", ".join(header))

    ours = [(pid, p) for pid, p in players.items() if p.get("team", "ally") == team]
    theirs = [(pid, p) for pid, p in players.items() if p.get("team", "ally") != team]
    if ours:
        lines.append(f"Your team ({team}):")
        lines.extend("  - " + _fmt_player(pid, p) for pid, p in ours)
    if theirs:
        lines.append("Enemy team:")
        lines.extend("  - " + _fmt_player(pid, p) for pid, p in theirs)

    events = state.get("events") or []
    if events:
        lines.append("Recent events:")
        lines.extend(f"  - {e}" for e in events[-6:])
    return "\n".join(lines)


def _team_food(state: dict[str, Any], team: str) -> int:
    total = 0
    for p in (state or {}).get("players", {}).values():
        food = p.get("food")
        if p.get("team", "ally") == team and isinstance(food, str) and "/" in food:
            try:
                total += int(food.split("/")[0])
            except ValueError:
                pass
    return total


def summarize_outcome(
    prev_state: dict[str, Any] | None, cur_state: dict[str, Any], team: str
) -> str:
    """Strategy track S2 — what changed since the last plan, for the Strategist.

    Coarse but honest signals (army trend via food + the latest events). Real
    richness arrives with live game state in M5+; the interface holds.
    """
    if not prev_state:
        return "first plan; no prior outcome yet."
    ours_prev, ours_cur = _team_food(prev_state, team), _team_food(cur_state, team)
    trend = "grew" if ours_cur > ours_prev else "shrank" if ours_cur < ours_prev else "held"
    parts = [f"Your army {trend} (food {ours_prev}→{ours_cur})."]
    events = (cur_state or {}).get("events") or []
    if events:
        parts.append("Recent: " + "; ".join(str(e) for e in events[-3:]))
    return " ".join(parts)


def build_user_prompt(
    state_summary: str,
    chat_history: list[dict[str, Any]],
    team_plan: str | None = None,
) -> str:
    """Assemble the per-turn persona message: state + team plan + recent chat."""
    parts = ["[GAME STATE]", state_summary]
    if team_plan:
        parts += ["", "[YOUR TEAM'S PLAN]", team_plan,
                  "(align your chat and directive with this plan)"]
    parts += ["", "[RECENT CHAT]"]
    if chat_history:
        for line in chat_history:
            parts.append(f"{line['speaker']}: {line['text']}")
    else:
        parts.append("(quiet so far)")
    parts.append("")
    parts.append(
        "Respond with a single JSON object: "
        '{"say_in_chat": str|null, "say_aloud": str|null, '
        '"directive": {"strategy": str|null, "aggression": number|null, '
        '"target_player": str|null}|null, "thinking": str|null}. '
        "Stay in character. Most turns you should say little or nothing."
    )
    return "\n".join(parts)
