"""The Hub: shared chat history, latest game state, directive log, voice queue,
and the wake-routing that decides which personas react to what (design §7, §9).

Wake sources:
  - mention   : a human or persona names a persona  -> priority wake (bypasses idle throttle)
  - event     : a major game event (hero death, base lost, broadcast banter prompt)
  - idle      : each persona's own jittered banter timer (handled in persona loops)

Loop damping: an AI replies to another AI at most `ai_to_ai_turn_cap` times in a
run before falling silent; a broadcast event wakes only one randomly-chosen
eligible persona (the duplicate-response arbiter).
"""
from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Optional

from .config import Config
from .persona import Persona
from .schema import Directive

SpeakerKind = Literal["human", "ai", "system"]


@dataclass
class ChatLine:
    speaker: str
    text: str
    kind: SpeakerKind
    ts: float

    def as_dict(self) -> dict[str, Any]:
        return {"speaker": self.speaker, "text": self.text, "kind": self.kind}


@dataclass
class DirectiveRecord:
    persona: str
    player_id: int
    directive: Directive
    ts: float


class Hub:
    def __init__(self, config: Config, *, rng: random.Random | None = None) -> None:
        self.config = config
        self.personas: list[Persona] = []
        self._by_name: dict[str, Persona] = {}
        self.chat: deque[ChatLine] = deque(maxlen=config.chat_history_limit)
        self.latest_state: dict[str, Any] = {}
        self.directives: list[DirectiveRecord] = []
        self.team_plans: dict[str, Any] = {}  # team -> GamePlan (Strategy track S1)
        self.voice_out: asyncio.Queue[tuple[Persona, str]] = asyncio.Queue()
        self._rng = rng or random.Random()
        # Optional render hook, invoked the moment a line is posted so console
        # output stays in true chronological order. (line, source_persona|None)
        self.on_line: Optional[Callable[[ChatLine, Optional[Persona]], None]] = None

    # --- registration ---
    def register(self, personas: Iterable[Persona]) -> None:
        self.personas = list(personas)
        self._by_name = {p.name.lower(): p for p in self.personas}

    # --- reads for the persona loop ---
    def recent_chat(self, limit: int | None = None) -> list[dict[str, Any]]:
        limit = limit or self.config.history_for_prompt
        return [line.as_dict() for line in list(self.chat)[-limit:]]

    # --- state ---
    def set_state(self, state: dict[str, Any]) -> None:
        self.latest_state = state

    # --- team plans (Strategy track S1) ---
    def set_plan(self, team: str, plan: Any) -> None:
        self.team_plans[team] = plan

    def plan_for(self, team: str) -> Any | None:
        return self.team_plans.get(team)

    # --- writes / routing ---
    def post_chat(self, speaker: str, text: str, kind: SpeakerKind, *, source: Optional[Persona] = None) -> None:
        """Record a chat line and wake any personas named in it."""
        self.chat.append(ChatLine(speaker=speaker, text=text, kind=kind, ts=time.time()))
        if self.on_line:
            self.on_line(self.chat[-1], source)
        self._route_mentions(text, kind, source)

    def _route_mentions(self, text: str, kind: SpeakerKind, source: Optional[Persona]) -> None:
        for persona in self.personas:
            if source is not None and persona is source:
                continue
            if not persona.mentioned_in(text):
                continue
            if kind == "ai":
                # AI->AI: respect the turn cap so two bots don't loop forever.
                speaker_key = source.name if source else "?"
                count = persona.ai_reply_counts.get(speaker_key, 0)
                if count >= self.config.ai_to_ai_turn_cap:
                    continue
                persona.ai_reply_counts[speaker_key] = count + 1
            else:
                # a human spoke -> reset the AI->AI counters, the conversation moved on
                persona.ai_reply_counts.clear()
            persona.trigger(priority=True)

    def emit_event(self, text: str, *, wake: Optional[list[str]] = None, broadcast: bool = False) -> None:
        """Record a game event and wake personas.

        - wake=[names]: wake exactly those personas (priority).
        - broadcast=True: wake a single randomly-chosen persona (arbiter), so a
          map-wide moment doesn't make everyone pile on at once.
        """
        self.chat.append(ChatLine(speaker="*event*", text=text, kind="system", ts=time.time()))
        if self.on_line:
            self.on_line(self.chat[-1], None)
        targets: list[Persona] = []
        if wake:
            wanted = {n.lower() for n in wake}
            targets = [p for p in self.personas if p.name.lower() in wanted]
        elif broadcast and self.personas:
            targets = [self._rng.choice(self.personas)]
        for p in targets:
            p.trigger(priority=True)

    def record_directive(self, persona: Persona, directive: Directive) -> None:
        self.directives.append(
            DirectiveRecord(persona=persona.name, player_id=persona.player_id, directive=directive, ts=time.time())
        )
