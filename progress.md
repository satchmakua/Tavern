# Tavern — Progress

Living status log. Update as milestones move. See [roadmap.md](roadmap.md) for the full plan.

**Current phase:** 🚧 Strategy track S2 — grounding + feedback + controlled vocab, verified on real model
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
| **S1 — Strategist loop** | ✅ Built | Per-team `Strategist` + `GamePlan`, separate from banter; personas derive directives from the plan. Posture-anchored aggression (no more pinned 1.0), plan adapts to human calls + events. |
| **S2 — Grounding + feedback + vocab** | ✅ Built | `directives.py` normalizes free-form → controlled vocab (§4); `knowledge.py` injects race/matchup/timing grounding; `summarize_outcome` feeds prior-plan results back. Real model: grounded reasoning ("enemy expanding at eastern gold mine"), canonical intents, normalized persona directives. |
| S3 — Widen control surface | ⬜ Not started | Co-designed with M6 |
| S4 — Stronger strategist model | ⬜ Not started | 14B/32B or 2nd machine; `TAVERN_STRATEGIST_MODEL` already overrides |

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
- **2026-06-26** — Added the **Strategy track (S1–S4)** to the roadmap as first-class work, then built **S1**: `tavern/strategy.py` (`GamePlan`, `Strategist`, team summary), per-team strategist loop in `main.py`, plan rendered + injected into persona prompts. On the real model the strategist sets a plan, **adapts it to human calls/events with reasoning**, and personas track its posture (aggression 0.5→0.9 instead of pinned 1.0).
- **2026-06-26** — Built **S2**: `directives.py` (free-form → controlled-vocab normalization, positional keyword match + clean-token pass-through), `knowledge.py` (race/matchup/timing grounding injected per board), `summarize_outcome` (army-trend + events feedback between plans). 35 tests pass. Real model shows grounded, adapting plans with canonical intents; persona directives normalized to §4 vocab.

## In progress

- **Strategy track** — S1+S2 built. **S3** (widen control surface) is co-designed with **M6** (AMAI hooks), so it waits for the bridge. **S4** (stronger strategist model) is a config flip (`TAVERN_STRATEGIST_MODEL`) worth A/B-ing once a 14B is pulled.

## Next up

1. **M3 — Voice frontend** (`/daemon` voice in/out): wire the installed whisper.cpp + Piper, push-to-talk (`pynput`), per-device speaker tagging, one-voice-at-a-time. Tool paths are already in `config.py`. The next buildable milestone without the game.
2. **S4 spot-check** (optional, cheap): pull a 14B, set `TAVERN_STRATEGIST_MODEL`, and compare plan quality vs the 8B.
3. **Persona/strategist tuning** against the real models (cadence, trash-talk, posture calibration).

## Blockers / open questions

- ~~Confirm exact Ollama tags~~ — **resolved 2026-06-26**: `llama3.1:8b-instruct` is 404; canonical tags are **`llama3.1:8b`** and **`qwen2.5:7b-instruct`** (registry-verified). Code/scripts updated.

## Decisions log

- **2026-06-25** — Following design v2: `war3_lua` is the backbone bridge (not optional); AI speech renders via `BlzDisplayChatMessage` through `BlzSendSyncData` (never injected as chat); LAN-only (Battle.net disqualified); MIT license.
