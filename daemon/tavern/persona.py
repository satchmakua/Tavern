"""Persona definitions (loaded from /personas/*.yaml) plus per-persona runtime state."""
from __future__ import annotations

import asyncio
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Persona:
    """One AI player: its static definition plus mutable runtime state.

    The static fields come straight from the YAML; everything below `--- runtime`
    is owned by the daemon while a game is live.
    """

    # --- static (from YAML) ---
    name: str
    player_id: int
    race: str = ""
    team: str = "ally"            # "ally" | "enemy"
    temperament: str = ""
    model: str = ""               # Ollama model tag; "" -> daemon default
    voice: str = ""               # Piper voice id
    idle_banter_seconds: Optional[float] = None
    system_prompt: str = ""
    source_path: Optional[Path] = None

    # --- runtime ---
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    priority_wake: bool = False           # set when woken by a mention/event (bypasses idle throttle)
    last_chat_ts: float = 0.0
    # consecutive AI->AI replies keyed by the other persona's name (for the turn cap)
    ai_reply_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._name_re = re.compile(rf"\b{re.escape(self.name.lower())}\b")

    def mentioned_in(self, text: str) -> bool:
        return bool(self._name_re.search(text.lower()))

    def trigger(self, *, priority: bool) -> None:
        """Wake this persona's loop. `priority` survives until consumed."""
        if priority:
            self.priority_wake = True
        self.wake.set()

    def consume_wake(self) -> bool:
        """Clear the wake flag and return whether it was a priority (mention/event) wake."""
        was_priority = self.priority_wake
        self.priority_wake = False
        self.wake.clear()
        return was_priority

    @property
    def is_ally(self) -> bool:
        return self.team.lower() == "ally"


_REQUIRED = ("name", "player_id", "system_prompt")


def load_persona_file(path: Path) -> Persona:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing = [k for k in _REQUIRED if k not in raw or raw[k] in (None, "")]
    if missing:
        raise ValueError(f"{path.name}: missing required field(s): {', '.join(missing)}")
    return Persona(
        name=str(raw["name"]),
        player_id=int(raw["player_id"]),
        race=str(raw.get("race", "")),
        team=str(raw.get("team", "ally")),
        temperament=str(raw.get("temperament", "")),
        model=str(raw.get("model", "")),
        voice=str(raw.get("voice", "")),
        idle_banter_seconds=(
            float(raw["idle_banter_seconds"]) if raw.get("idle_banter_seconds") is not None else None
        ),
        system_prompt=str(raw["system_prompt"]).strip(),
        source_path=path,
    )


def load_personas(personas_dir: Path) -> list[Persona]:
    """Load every *.yaml in the personas directory, sorted by player_id."""
    files = sorted(p for p in personas_dir.glob("*.yaml") if p.is_file())
    personas = [load_persona_file(p) for p in files]
    ids = [p.player_id for p in personas]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate player_id(s) across personas: {sorted(dupes)}")
    personas.sort(key=lambda p: p.player_id)
    return personas
