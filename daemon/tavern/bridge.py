"""Phase D — the file channel between the daemon and the WC3 map (design §5).

Two halves, both `.txt` files in the map's `CustomMapData` folder, exchanged via
w3ts `File` (the Preload exploit). See docs/bridge-protocol.md.

  - **TavernDirective.txt** (daemon → game): pipe-delimited lines the map parses —
    `CHAT|id|persona|text` and `DIR|player|strategy|aggression|target`. Written by
    `DirectiveWriter`.
  - **TavernState.txt** (game → daemon): a JSON state snapshot + any new human chat,
    read by `StateFileWatcher` and fed into the Hub like `FakeStateEmitter`.

With `wc3=True`, the daemon wraps/unwraps the w3ts `File` on-disk format (`wc3codec`)
so the real map can read/write the files. With `wc3=False` the files are raw text —
used for offline (`--fake-llm`) Stage-A testing. Writes are atomic (temp + os.replace).
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
from .wc3codec import decode_file, encode_file


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)  # atomic on the same volume


def _san(s: str) -> str:
    """Keep pipe-delimited fields intact."""
    return s.replace("|", "/").replace("\n", " ").replace("\r", " ")


class DirectiveWriter:
    """Collects what the daemon wants the map to do and flushes it as delimited lines.

    Driven by Hub hooks (no new plumbing in the loops): `note_chat` off `hub.on_line`
    captures AI chat lines; `note_directive` off `hub.on_directive` captures per-player
    directives.
    """

    def __init__(self, bridge_dir: Path, hub: Hub, config: Config, *, wc3: bool = False) -> None:
        self.dir = bridge_dir
        self.path = bridge_dir / config.directive_file_name
        self.cursor_path = bridge_dir / config.directive_cursor_name
        self.hub = hub
        self.wc3 = wc3
        self._seq_prefix = config.directive_seq_prefix
        self._keep = config.directive_seq_keep
        self._seq = 0
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
        # plans aren't sent to the map (the map switches on per-player directives).
        return

    def _payload(self) -> str:
        lines: list[str] = []
        for c in self._chat:
            lines.append(f"CHAT|{c['id']}|{_san(c['persona'])}|{_san(c['text'])}")
        for pid, d in self._directives.items():
            aggr = d.get("aggression")
            lines.append(
                f"DIR|{pid}|{_san(d.get('strategy') or '')}|"
                f"{'' if aggr is None else aggr}|{_san(d.get('target_player') or '')}"
            )
        return "\n".join(lines)

    def flush(self) -> bool:
        if not self._dirty:
            return False
        content = self._payload()
        try:
            if self.wc3:
                self._write_seq(content)
            else:
                _atomic_write(self.path, content)
        except OSError:
            return False  # transient lock (e.g. OneDrive syncing) — retry next tick
        self._dirty = False
        return True

    def _write_seq(self, content: str) -> None:
        """Rotating-filename write to defeat the Preload cache bug; a cursor file lets
        the map skip the backlog (seq) and pre-game chat (maxChatId) at start."""
        seq = self._seq
        _atomic_write(self.dir / f"{self._seq_prefix}{seq}.txt", encode_file(content))
        max_chat_id = self._next_id - 1
        _atomic_write(self.cursor_path, encode_file(f"{seq}|{max_chat_id}"))
        old = seq - self._keep
        if old >= 0:
            try:
                (self.dir / f"{self._seq_prefix}{old}.txt").unlink()
            except OSError:
                pass
        self._seq = seq + 1

    async def run(self) -> None:
        self.flush()  # ensure the file exists immediately
        while True:
            await asyncio.sleep(self._flush_interval)
            self.flush()


class StateFileWatcher:
    """Tails TavernState.txt and feeds changes into the Hub (mirrors FakeStateEmitter)."""

    def __init__(self, bridge_dir: Path, hub: Hub, config: Config, *, wc3: bool = False) -> None:
        self.path = bridge_dir / config.state_file_name
        self.hub = hub
        self.wc3 = wc3
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
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return False
        text: Optional[str] = raw
        if self.wc3:
            text = decode_file(raw)  # unwrap the w3ts File format
            if text is None:
                return False  # not a complete File yet (mid-write)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False  # half-written; retry next poll
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
