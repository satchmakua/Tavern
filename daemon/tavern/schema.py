"""The persona output contract (design §4) and tolerant parsing of LLM JSON.

Every persona turn returns one JSON object:

    {
      "say_in_chat": "rax done, going treants",
      "say_aloud": null,
      "directive": {"strategy": "expand_now", "aggression": 0.3, "target_player": null},
      "thinking": "teammate just lost their altar, hold the push"
    }

`thinking` is logged for debugging and read by nothing. The daemon acts on the rest.
"""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class Directive(BaseModel):
    """Coarse strategic intent the Bridge translates into AMAI nudges (design §4)."""

    model_config = ConfigDict(extra="ignore")

    strategy: Optional[str] = None       # e.g. expand_now, tech_up, mass_grunt, defend, creep_more
    aggression: Optional[float] = None   # 0..1, dials AMAI's existing aggression knob
    target_player: Optional[str] = None  # for attack_<player> intents

    @field_validator("aggression")
    @classmethod
    def _clamp_aggression(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return max(0.0, min(1.0, float(v)))

    @field_validator("strategy", "target_player")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    def is_empty(self) -> bool:
        return self.strategy is None and self.aggression is None and self.target_player is None


class PersonaOutput(BaseModel):
    """One persona's decision for a single turn."""

    model_config = ConfigDict(extra="ignore")

    say_in_chat: Optional[str] = None
    say_aloud: Optional[str] = None
    directive: Optional[Directive] = None
    thinking: Optional[str] = None

    @field_validator("say_in_chat", "say_aloud", "thinking")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @field_validator("directive")
    @classmethod
    def _drop_empty_directive(cls, v: Optional[Directive]) -> Optional[Directive]:
        if v is None or v.is_empty():
            return None
        return v

    def is_silent(self) -> bool:
        return (
            self.say_in_chat is None
            and self.say_aloud is None
            and self.directive is None
        )


class OutputParseError(ValueError):
    """Raised when an LLM response can't be coerced into PersonaOutput."""


def _extract_json(raw: str) -> str:
    """Pull a JSON object out of an LLM response, tolerating code fences and prose."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            first, rest = text.split("\n", 1)
            # drop a leading language tag like ```json
            if first.strip().lower() in {"json", ""}:
                text = rest
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_output(raw: str) -> PersonaOutput:
    """Parse + validate an LLM response into PersonaOutput. Raises OutputParseError."""
    snippet = _extract_json(raw)
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as e:
        raise OutputParseError(f"not valid JSON: {e}; raw={raw!r}") from e
    if not isinstance(data, dict):
        raise OutputParseError(f"expected a JSON object, got {type(data).__name__}: {raw!r}")
    try:
        return PersonaOutput.model_validate(data)
    except Exception as e:  # pydantic ValidationError
        raise OutputParseError(f"schema validation failed: {e}; raw={raw!r}") from e
