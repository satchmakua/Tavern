# /daemon — Companion Daemon + Voice Frontend (Python)

Host-side, outside the WC3 sandbox. See [design §9](../tavern-design.md) and [§3](../tavern-design.md).

**Companion Daemon** — a single asyncio process: one coroutine per persona (each with its own state, history, rate limit), a file-watcher on the map's state file, a queue subscriber for transcribed voice, a directive-file writer, a bounded shared chat history, and a state summarizer (raw snapshot → ~15–20 lines per player perspective).

**Voice Frontend** — `whisper.cpp` (`base.en`) + `silero-vad` for speech-in, Piper for speech-out. Push-to-talk via `pynput`, per-device speaker tagging, one-voice-at-a-time. Never touches the game sandbox. _(Not built yet — M3.)_

Talks to the LLM via Ollama at `http://localhost:11434`.

## Status

M1/M2 core is in place and runs **offline** (no Ollama needed) via a fake LLM:

- `tavern/schema.py` — persona output contract (`PersonaOutput`/`Directive`) + tolerant JSON parsing
- `tavern/persona.py` — `Persona` (static YAML + runtime state) and the loader
- `tavern/hub.py` — shared chat history, game state, directive log, voice queue, wake-routing (mentions, events, AI↔AI turn cap, broadcast arbiter)
- `tavern/summarizer.py` — player-scoped state → NL summary
- `tavern/llm.py` — `OllamaClient` (native `/api/chat`, `format: json`) and `FakeLLM`
- `tavern/fakestate.py` — replays a scripted scenario into the Hub on a timer
- `tavern/main.py` — wires it together with a console renderer

## Quickstart

```bash
cd daemon
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # macOS/Linux

# Run the whole loop offline against the sample scenario — no Ollama required:
python -m tavern --fake-llm

# Faster, deterministic playback:
python -m tavern --fake-llm --speed 4 --seed 1

# Once Ollama is up (see ../scripts/setup.ps1), drop --fake-llm to use a real model:
python -m tavern --persona Dakkar            # M1: one persona
python -m tavern                             # all personas in /personas

# Tests:
python -m pytest
```

### Useful flags

| Flag | Effect |
|---|---|
| `--fake-llm` | run with a canned LLM (no Ollama) |
| `--scenario PATH` \| `none` | FakeState scenario JSON (default `scenarios/skirmish.json`) |
| `--persona NAME` | limit to one or more personas (repeatable) |
| `--speed N` | scenario playback speed multiplier |
| `--duration N` | run for N seconds (default: scenario length + tail) |
| `--model` / `--host` | override Ollama model / host |
| `--seed N` | deterministic banter, arbiter, fake-llm |

Personas live in [`../personas`](../personas); scenarios in [`scenarios/`](scenarios). Config defaults and env overrides (`TAVERN_OLLAMA_HOST`, `TAVERN_MODEL`, …) are in `tavern/config.py`.
