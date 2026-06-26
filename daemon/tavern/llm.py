"""LLM clients. OllamaClient talks to a local Ollama; FakeLLM runs the loop offline.

Ollama's native /api/chat with `"format": "json"` gives constrained JSON decoding,
which is what the directive channel needs. (The OpenAI-compatible /v1 endpoint at the
same host is also available, but native json-format is the most reliable here.)
"""
from __future__ import annotations

import json
import random
from typing import Protocol

import httpx


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    async def complete(self, *, model: str, system: str, user: str) -> str: ...
    async def warmup(self, *, model: str) -> None: ...
    async def aclose(self) -> None: ...


class OllamaClient:
    def __init__(self, host: str, timeout: float, temperature: float = 0.8, keep_alive: str = "30m") -> None:
        self._client = httpx.AsyncClient(base_url=host.rstrip("/"), timeout=timeout)
        self._temperature = temperature
        self._keep_alive = keep_alive

    async def complete(self, *, model: str, system: str, user: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"temperature": self._temperature},
        }
        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Ollama returned {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"could not reach Ollama at {self._client.base_url}: {e}") from e
        return resp.json()["message"]["content"]

    async def warmup(self, *, model: str) -> None:
        """Load a model into VRAM ahead of time so the first real turn isn't cold."""
        try:
            resp = await self._client.post(
                "/api/generate", json={"model": model, "keep_alive": self._keep_alive}
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Ollama returned {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"could not reach Ollama at {self._client.base_url}: {e}") from e

    async def aclose(self) -> None:
        await self._client.aclose()


class FakeLLM:
    """Offline stand-in so the whole pipeline runs without Ollama installed.

    Returns deterministic-ish, schema-valid JSON. Good for exercising gating,
    routing, rate limits, and rendering before a model is available.
    """

    _LINES = [
        "rax done, going aggressive",
        "watch their expo, i'll feint north",
        "need 30s for my second hero",
        "creeping the green camp, back soon",
        "nice, that push folded",
        "teching now, hold them off",
    ]
    _STRATS = ["expand_now", "tech_up", "mass_grunt", "defend", "creep_more"]
    _PHASES = ["opening", "early", "mid", "late"]
    _OBJECTIVES = ["pressure their natural", "secure a fast expansion", "tech to tier 2 then push",
                   "defend and creep for XP", "mass air and contain"]

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    async def complete(self, *, model: str, system: str, user: str) -> str:
        if "[STRATEGIST]" in user:  # a Strategist call expects a GamePlan
            return json.dumps({
                "phase": self._rng.choice(self._PHASES),
                "intent": self._rng.choice(self._STRATS),
                "objective": self._rng.choice(self._OBJECTIVES),
                "target_player": None,
                "posture": round(self._rng.random(), 2),
                "tech_goal": self._rng.choice(["tier2", "air", "casters", None]),
                "rationale": "(fake-llm plan)",
            })
        # Pull the persona's name out of the system prompt for a touch of flavor.
        say = self._rng.choice(self._LINES)
        out: dict = {"say_in_chat": say, "say_aloud": None, "thinking": "(fake-llm)"}
        if self._rng.random() < 0.4:
            out["directive"] = {
                "strategy": self._rng.choice(self._STRATS),
                "aggression": round(self._rng.random(), 2),
                "target_player": None,
            }
        if self._rng.random() < 0.1:
            out["say_aloud"] = "let's go!"
        return json.dumps(out)

    async def warmup(self, *, model: str) -> None:
        return None

    async def aclose(self) -> None:
        return None
