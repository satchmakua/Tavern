"""Phase D — the file channel between the daemon and the WC3 map (design §5).

Two halves, both plain JSON files in a shared `bridge_dir` that `war3_lua` can
read/write from inside the map:

  - **directive.json** (daemon → game): persona chat lines to render, per-player
    AMAI directives, and the current team plans. Written by `DirectiveWriter`.
  - **state.json** (game → daemon): a game-state snapshot + any new human chat.
    Read by `StateFileWatcher`, which feeds it into the Hub exactly like the
    `FakeStateEmitter` does for scripted scenarios.

Both sides write atomically (temp file + os.replace) so the reader never sees a
half-written file. See docs/bridge-protocol.md for the wire format.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from .config import Config
from .hub import ChatLine, DirectiveRecord, Hub
from .persona import Persona


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # atomic on the same volume


class DirectiveWriter:
    """Collects what the daemon wants the map to do and flushes it to directive.json.

    Driven by Hub hooks (no new plumbing in the loops): `note_chat` off `hub.on_line`
    captures AI chat lines; `note_directive` off `hub.on_directive` captures per-player
    directives. Team plans are read from `hub.team_plans` at flush time.
    """

    def __init__(self, bridge_dir: Path, hub: Hub, config: Config) -> None:
        self.path = bridge_dir / config.directive_file_name
        self.hub = hub
        self._chat_limit = config.directive_chat_limit
        self._flush_interval = config.directive_flush_interval
        self._chat: list[dict[str, Any]] = []
        self._next_id = 1
        self._directives: dict[str, dict[str, Any]] = {}
        self._dirty = True  # write once at startup so the file always exists

    def note_chat(self, line: ChatLine, source: Optional[Persona]) -> None:
        if line.kind != "ai" or source is None:
            return
        self._chat.append({"id": self._next_id, "persona": source.name, "text": line.text})
        self._next_id += 1
        if len(self._chat) > self._chat_limit:
            self._chat = self._chat[-self._chat_limit :]
        self._dirty = True

    def note_directive(self, rec: DirectiveRecord) -> None:
        d = rec.directive
        self._directives[str(rec.player_id)] = {
            "strategy": d.strategy,
            "aggression": d.aggression,
            "target_player": d.target_player,
        }
        self._dirty = True

    def note_plan(self, team: str, plan: Any) -> None:
        # plans are read live from hub.team_plans at flush; just mark dirty.
        self._dirty = True

    def _payload(self) -> dict[str, Any]:
        plans = {team: plan.model_dump() for team, plan in self.hub.team_plans.items()}
        return {"chat": self._chat, "directives": self._directives, "plan": plans}

    def flush(self) -> bool:
        if not self._dirty:
            return False
        _atomic_write_json(self.path, self._payload())
        self._dirty = False
        return True

    async def run(self) -> None:
        self.flush()  # ensure the file exists immediately
        while True:
            await asyncio.sleep(self._flush_interval)
            self.flush()


class StateFileWatcher:
    """Tails state.json and feeds changes into the Hub (mirrors FakeStateEmitter)."""

    def __init__(self, bridge_dir: Path, hub: Hub, config: Config) -> None:
        self.path = bridge_dir / config.state_file_name
        self.hub = hub
        self._interval = config.state_poll_interval
        self._last_mtime: Optional[float] = None

    def poll_once(self) -> bool:
        """Read the state file if it changed; return True if applied."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return False
        if mtime == self._last_mtime:
            return False
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False  # likely a half-written file; retry next poll
        self._last_mtime = mtime
        self._apply(data)
        return True

    def _apply(self, data: dict[str, Any]) -> None:
        new_chat = data.pop("new_chat", None) or []
        self.hub.set_state(data)
        for entry in new_chat:
            text = entry.get("text")
            if text:
                self.hub.post_chat(entry.get("speaker", "player"), text, kind="human")

    async def run(self) -> None:
        while True:
            self.poll_once()
            await asyncio.sleep(self._interval)
