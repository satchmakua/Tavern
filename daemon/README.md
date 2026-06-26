# /daemon — Companion Daemon + Voice Frontend (Python)

Host-side, outside the WC3 sandbox. See [design §9](../tavern-design.md) and [§3](../tavern-design.md).

**Companion Daemon** — a single asyncio process: one coroutine per persona (each with its own state, history, rate limit), a file-watcher on the map's state file, a queue subscriber for transcribed voice, a directive-file writer, a bounded shared chat history, and a state summarizer (raw snapshot → ~15–20 lines per player perspective).

**Voice Frontend** (`tavern/voice.py`, M3) — Piper for speech-out (`say_aloud` → real audio, one voice at a time, per-persona voice aliasing), whisper.cpp for speech-in via **push-to-talk** (`pynput` key-hold → `sounddevice` 16 kHz capture → whisper → human chat, tagged by speaker/device). Never touches the game sandbox. Enable input with `--voice`; `--no-audio` prints voice lines instead of playing them. **Use headsets, not room speakers** — open mics + TTS create a feedback loop (design §3). Add more voices by dropping `.onnx` files in `tools/piper/voices` and mapping them in `voice.py`.

Talks to the LLM via Ollama at `http://localhost:11434`.

## Status

M1/M2 core is in place and runs **offline** (no Ollama needed) via a fake LLM:

- `tavern/schema.py` — persona output contract (`PersonaOutput`/`Directive`) + tolerant JSON parsing
- `tavern/persona.py` — `Persona` (static YAML + runtime state) and the loader
- `tavern/hub.py` — shared chat history, game state, directive log, voice queue, wake-routing (mentions, events, AI↔AI turn cap, broadcast arbiter), per-team game plans
- `tavern/strategy.py` — **Strategy track S1**: per-team `Strategist` + `GamePlan` (deliberate planner, separate from banter); personas derive their chat/directives from the team plan
- `tavern/directives.py` — **S2**: normalize free-form intents → controlled vocabulary (design §4) for the Bridge/AMAI
- `tavern/knowledge.py` — **S2**: compact RTS grounding (race/matchup/timing) injected into the strategist prompt
- `tavern/summarizer.py` — player-scoped state → NL summary, team-scoped summary for the strategist, and `summarize_outcome` (S2 plan feedback)
- `tavern/llm.py` — `OllamaClient` (native `/api/chat`, `format: json`) and `FakeLLM`
- `tavern/voice.py` — **M3**: `PiperTTS` (speech-out), `WhisperSTT` + `VoiceInput` (push-to-talk speech-in)
- `tavern/bridge.py` — **M5 (daemon half)**: `StateFileWatcher` + `DirectiveWriter` (file channel to/from the WC3 map; see [docs/bridge-protocol.md](../docs/bridge-protocol.md))
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
