# Tavern — Progress

Living status log. Update as milestones move. See [roadmap.md](roadmap.md) for the full plan.

**Current phase:** 🚧 M1/M2 — environment installed & verified; persona tuning next
**Last updated:** 2026-06-26

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| Kill test | ✅ Passed | Dakkar runs on real `llama3.1:8b` — in-character chat, valid JSON, directives, voice line. Thesis holds. |
| M0 — Repo + environment | ✅ Done | Ollama + `llama3.1:8b` + `qwen2.5:7b-instruct`, Piper (TTS), whisper.cpp (STT, base.en) all installed & smoke-tested. `setup.ps1` reproduces it. |
| M1 — One persona, chat-only | 🚧 In progress | Daemon verified against the real model end-to-end (17 tests pass; cold-start fixed via warmup). Remaining: persona tuning. |
| M2 — Multiple personas | 🚧 In progress | Structure already in: 4 personas, mention-routing, AI↔AI turn cap, broadcast arbiter; tuning pending |
| M3 — Voice in/out | ⬜ Not started | |
| M4 — Map + AMAI baseline | ⬜ Not started | |
| M5 — `war3_lua` file bridge | ⬜ Not started | |
| M6 — Sync hardening + AMAI hooks | ⬜ Not started | |
| M7 — Full 4v4 | ⬜ Not started | |
| M8 — Polish + packaging | ⬜ Not started | |

Legend: ⬜ not started · 🚧 in progress · ✅ done · ⛔ blocked

---

## Done

- **2026-06-25** — Design document v2 committed (`tavern-design.md`).
- **2026-06-25** — Project docs scaffolded: `readme.md`, `roadmap.md`, `progress.md`.
- **2026-06-26** — Repo skeleton scaffolded: `/daemon`, `/map-mod`, `/personas`, `/docs`, `/scripts` (each with a README), MIT `LICENSE`, `.gitignore`, and example persona `personas/dakkar.yaml`.
- **2026-06-26** — Added `scripts/setup.ps1`: pulls the Ollama models and verifies `:11434`.
- **2026-06-26** — Built the `/daemon` package (M1 core, M2 structure): `Persona`/`Hub`, Ollama client + `FakeLLM`, JSON schema + tolerant parsing, state summarizer, `FakeState` emitter, console renderer. Added 4 personas (Dakkar, Sera, Vex, Grollum) and a sample scenario. 17 pytest tests pass; full loop verified offline with `--fake-llm`.
- **2026-06-26** — **Installed the full toolchain** (RTX 5070 Ti, 12 GB, driver 610.47): Ollama 0.30.9 + `llama3.1:8b` + `qwen2.5:7b-instruct`; Piper TTS (2 voices) and whisper.cpp v1.9.1 (base.en) under `tools/`. All smoke-tested. `scripts/setup.ps1` now reproduces the whole environment.
- **2026-06-26** — **Kill test passed**: daemon on the real `llama3.1:8b` produces in-character chat, valid JSON, directives, and a spoken line. Added model **warmup + `keep_alive`** so the first turn isn't a cold-load (was causing initial silence).

## In progress

- **M1/M2 — persona tuning** (the high-leverage "make them feel alive" work). First-pass observation: Dakkar pins `aggression=1.0` every turn and emits free-form `strategy` strings rather than the controlled vocab — both are prompt/tuning fixes, not code bugs.

## Next up

1. **Tune the four personas** against the real models: temper the aggression, steer `strategy` toward the controlled vocabulary (design §4), dial per-persona cadence/trash-talk. Run `cd daemon; .\.venv\Scripts\python.exe -m tavern` (all personas) or `--persona <name>`.
2. **M3 — Voice frontend** (`/daemon` voice in/out): wire the installed whisper.cpp + Piper, push-to-talk (`pynput`), per-device speaker tagging, one-voice-at-a-time. Tool paths are already in `config.py`. Next *buildable* milestone without the game.

## Blockers / open questions

- ~~Confirm exact Ollama tags~~ — **resolved 2026-06-26**: `llama3.1:8b-instruct` is 404; canonical tags are **`llama3.1:8b`** and **`qwen2.5:7b-instruct`** (registry-verified). Code/scripts updated.

## Decisions log

- **2026-06-25** — Following design v2: `war3_lua` is the backbone bridge (not optional); AI speech renders via `BlzDisplayChatMessage` through `BlzSendSyncData` (never injected as chat); LAN-only (Battle.net disqualified); MIT license.
