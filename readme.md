# Tavern — AI Companions for Warcraft 3

> In Warcraft 3, the Tavern is where you hire the hero companions who fight at your side. This project is a Tavern for whole players: AI teammates and opponents who chat, listen to your voice, react to the map, strategize at the macro level, and trash-talk — good-naturedly.

The AI does the talking and the strategy; the existing [AMAI](https://github.com/SMUnlimited/AMAI) mod handles the unit micromanagement it's already good at. Everything here is **free, open source, and runs fully offline** once installed. Built for **LAN play** — so you can fill a 4v4 or FFA lobby without needing six more humans.

See [tavern-design.md](tavern-design.md) for the full design (v2).

---

## The one constraint

Warcraft 3's scripting sandbox (Lua/JASS) cannot open sockets, make HTTP requests, or normally touch the filesystem. So **the LLM cannot live inside the map.** It runs as a separate host-side process (the *Companion Daemon*) that talks to the game through an indirect file-based bridge. Everything in the architecture follows from this.

## Architecture

Five components across the sandbox boundary:

**Host side (outside the game):**
- **Companion Daemon** — Python (asyncio). The brain: one persona per AI player, talks to a local LLM via [Ollama](https://ollama.com/), decides what each persona says/does, manages the bridge.
- **Voice Frontend** — Python. `whisper.cpp` (speech-to-text) in, [Piper](https://github.com/rhasspy/piper) (text-to-speech) out. Fully decoupled from the game.

**Game side (inside a custom map):**
- **Tavern Bridge** — TypeScript compiled to Lua, baked into a modified melee map. Reads directives, renders persona chat, exfiltrates game state. Uses [`war3_lua`](https://github.com/Ev3nt/war3_lua) for file I/O.
- **Modified AMAI** — the open-source Advanced Melee AI, lightly forked so each AI player's broad strategy can be nudged at runtime.

```
        HOST PC
   ┌──────────────────────────────────────────────────────────┐
   │  ┌────────────┐      ┌────────────────┐     ┌──────────┐  │
   │  │   Voice    │─────▶│   Companion    │────▶│  Ollama  │  │
   │  │  Frontend  │◀─────│     Daemon     │◀────│ (LLM)    │  │
   │  └─────┬──────┘      └───┬────────▲───┘     └──────────┘  │
   │     headset             directive   state +               │
   │   (mic + phones)          file      chat file             │
   │  ════════════════════════╪════════╪═════════════════════  │ ← sandbox
   │                          ▼        │                        │   boundary
   │  ┌─────────────────────────────────────────────────────┐  │
   │  │           Warcraft 3 Reforged (LAN host)            │  │
   │  │   custom map:  Tavern Bridge (Lua via war3_lua)     │  │
   │  │                + modified AMAI                       │  │
   │  └─────────────────────────────────────────────────────┘  │
   └──────────────────────────────────────────────────────────┘
```

## Repo layout

| Path | Contents |
|---|---|
| `/daemon` | Companion Daemon + Voice Frontend (Python) |
| `/map-mod` | Tavern Bridge (TypeScript → Lua) + AMAI fork |
| `/personas` | One persona definition per AI player (YAML) |
| `/docs` | Design notes and reference material |
| `/scripts` | Launchers and dev tooling |

## Status

🚧 **M1/M2 — environment installed, kill test passed.** The full toolchain is set up (Ollama + `llama3.1:8b` + `qwen2.5:7b-instruct`, Piper TTS, whisper.cpp STT) and the Companion Daemon runs the persona loop against the **real** model — in-character chat, valid JSON directives, and spoken lines all work. It also runs fully offline with `--fake-llm`. Reproduce the environment with [`scripts/setup.ps1`](scripts/setup.ps1); run the brain with `cd daemon && python -m tavern --persona Dakkar`. See [daemon/README.md](daemon/README.md), [roadmap.md](roadmap.md), and [progress.md](progress.md).

The remaining M1/M2 work is **persona tuning** — making each AI feel alive and not annoying.

The very first thing to do is the **kill test** (design §14): install Ollama, pull `llama3.1:8b-instruct`, and roleplay an aggressive Orc player named Dakkar against a fake game state. If it feels in-character and fun, the thesis holds and the rest is engineering. If it feels flat on this hardware, the project stops there.

## Requirements

- Warcraft 3 Reforged (LAN; this project disqualifies Battle.net by design)
- A GPU with ≥8 GB VRAM for the 8B model, 16 GB RAM minimum / 32 GB comfortable
- [Ollama](https://ollama.com/) with `llama3.1:8b` and `qwen2.5:7b-instruct`
- `whisper.cpp` (`base.en`) and Piper for voice
- Headsets (not room speakers) — required to avoid the TTS→mic feedback loop

The LLM + voice toolchain is installed/reproduced by [`scripts/setup.ps1`](scripts/setup.ps1) (Ollama via winget, model pulls, Piper + whisper.cpp into `tools/`).

## License

MIT for this project's code, crediting AMAI and the underlying tools. Distribute code, not Blizzard assets. Keep it LAN-private and unofficial.
