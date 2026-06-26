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


def build_user_prompt(state_summary: str, chat_history: list[dict[str, Any]]) -> str:
    """Assemble the per-turn user message: state summary + recent chat."""
    parts = ["[GAME STATE]", state_summary, "", "[RECENT CHAT]"]
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
