"""FakeState emitter: replays a scripted scenario into the Hub on a timer, so the
daemon can be built and tuned with the game closed (design M1).

Scenario file (JSON):

    {
      "map": "(4) Lost Temple",
      "timeline": [
        {"at": 1,  "state": { ... full snapshot ... }},
        {"at": 3,  "chat":  [{"speaker": "you", "text": "dakkar push with me", "kind": "human"}]},
        {"at": 8,  "event": {"text": "Dakkar's Blademaster reached level 2", "wake": ["Dakkar"]}},
        {"at": 12, "event": {"text": "a hero died near mid", "broadcast": true}}
      ]
    }

`at` is seconds from emitter start. Steps fire in time order. A `state` step
replaces the Hub's latest snapshot; `chat` and `event` steps inject lines/events.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .hub import Hub


class FakeStateEmitter:
    def __init__(self, hub: Hub, scenario_path: Path, *, speed: float = 1.0) -> None:
        self.hub = hub
        self.scenario_path = scenario_path
        self.speed = speed
        self._timeline = self._load()

    def _load(self) -> list[dict[str, Any]]:
        data = json.loads(self.scenario_path.read_text(encoding="utf-8"))
        timeline = data.get("timeline", [])
        return sorted(timeline, key=lambda s: float(s.get("at", 0)))

    @property
    def duration(self) -> float:
        if not self._timeline:
            return 0.0
        return float(self._timeline[-1].get("at", 0)) / max(self.speed, 1e-6)

    async def run(self) -> None:
        start = asyncio.get_event_loop().time()
        for step in self._timeline:
            target = start + float(step.get("at", 0)) / max(self.speed, 1e-6)
            delay = target - asyncio.get_event_loop().time()
            if delay > 0:
                await asyncio.sleep(delay)
            self._apply(step)

    def _apply(self, step: dict[str, Any]) -> None:
        if "state" in step:
            self.hub.set_state(step["state"])
        for line in step.get("chat", []) or []:
            self.hub.post_chat(
                speaker=line.get("speaker", "you"),
                text=line["text"],
                kind=line.get("kind", "human"),
            )
        event = step.get("event")
        if event:
            self.hub.emit_event(
                event["text"],
                wake=event.get("wake"),
                broadcast=bool(event.get("broadcast", False)),
            )
