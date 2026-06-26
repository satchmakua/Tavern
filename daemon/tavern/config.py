"""Daemon configuration. Env vars override defaults; CLI overrides env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# repo_root/daemon/tavern/config.py  ->  parents[2] == repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PERSONAS_DIR = REPO_ROOT / "personas"
# Voice tooling installed per-machine by scripts/setup.ps1 (gitignored).
TOOLS_DIR = REPO_ROOT / "tools"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Config:
    # --- LLM / Ollama ---
    ollama_host: str = field(default_factory=lambda: _env("TAVERN_OLLAMA_HOST", "http://localhost:11434"))
    default_model: str = field(default_factory=lambda: _env("TAVERN_MODEL", "llama3.1:8b"))
    temperature: float = field(default_factory=lambda: float(_env("TAVERN_TEMPERATURE", "0.8")))
    request_timeout: float = field(default_factory=lambda: float(_env("TAVERN_TIMEOUT", "60")))
    # keep models resident in VRAM between turns so there's no per-turn reload
    keep_alive: str = field(default_factory=lambda: _env("TAVERN_KEEP_ALIVE", "30m"))

    # --- paths ---
    personas_dir: Path = field(
        default_factory=lambda: Path(_env("TAVERN_PERSONAS_DIR", str(DEFAULT_PERSONAS_DIR)))
    )

    # --- voice tooling (used by the M3 Voice Frontend; installed under <repo>/tools) ---
    piper_exe: Path = field(default_factory=lambda: TOOLS_DIR / "piper" / "piper.exe")
    piper_voices_dir: Path = field(default_factory=lambda: TOOLS_DIR / "piper" / "voices")
    whisper_exe: Path = field(default_factory=lambda: TOOLS_DIR / "whisper" / "Release" / "whisper-cli.exe")
    whisper_model: Path = field(default_factory=lambda: TOOLS_DIR / "whisper" / "models" / "ggml-base.en.bin")

    # --- strategist (Strategy track S1): the deliberate per-team planner ---
    strategist_model: str = field(default_factory=lambda: _env("TAVERN_STRATEGIST_MODEL", ""))  # "" -> default_model
    strategist_interval: float = 25.0   # base cadence for re-planning
    strategist_jitter: float = 5.0

    # --- gating / cadence (design §7, §9) ---
    idle_banter_seconds: float = 30.0   # base idle-banter interval per persona
    idle_banter_jitter: float = 12.0    # +/- jitter so personas don't sync up
    chat_min_interval: float = 6.0      # throttle: at most one idle chat line per persona per N s
    ai_to_ai_turn_cap: int = 3          # max consecutive AI->AI replies before both fall silent
    chat_history_limit: int = 50        # bounded shared chat history
    history_for_prompt: int = 10        # how many recent lines the LLM sees
