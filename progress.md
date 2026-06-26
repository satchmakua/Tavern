# Tavern — Progress

Living status log. Update as milestones move. See [roadmap.md](roadmap.md) for the full plan.

**Current phase:** 🚧 M3 voice built + M5 bridge daemon-half built; both verified. Game side needs Reforged + World Editor.
**Last updated:** 2026-06-26

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| Kill test | ✅ Passed | Dakkar runs on real `llama3.1:8b` — in-character chat, valid JSON, directives, voice line. Thesis holds. |
| M0 — Repo + environment | ✅ Done | Ollama + `llama3.1:8b` + `qwen2.5:7b-instruct`, Piper (TTS), whisper.cpp (STT, base.en) all installed & smoke-tested. `setup.ps1` reproduces it. |
| M1 — One persona, chat-only | 🚧 In progress | Daemon verified against the real model end-to-end (17 tests pass; cold-start fixed via warmup). Remaining: persona tuning. |
| M2 — Multiple personas | 🚧 In progress | Structure already in: 4 personas, mention-routing, AI↔AI turn cap, broadcast arbiter; tuning pending |
| M3 — Voice in/out | 🚧 Built | `voice.py`: `PiperTTS` (real say_aloud synthesis, persona-voice aliasing, one-at-a-time), `WhisperSTT` (verified on jfk.wav), `VoiceInput` (push-to-talk via pynput+sounddevice). `--voice`/`--no-audio` flags. Verified except live mic capture (needs a real mic + keypress). |
| M4 — Map + AMAI baseline | ⬜ Not started | Needs Reforged + World Editor (user); I scaffold wc3-ts-template + fetch AMAI |
| M5 — `war3_lua` file bridge | 🚧 Daemon half done | `bridge.py` (`StateFileWatcher` + `DirectiveWriter`), `--bridge DIR` mode, `docs/bridge-protocol.md`. **Stage A verified** (hand-written `state.json` → real-model `directive.json`). Map half pending. |
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
- **2026-06-26** — Built the **daemon half of the bridge** (M5, Phase D of the in-game-test plan): `tavern/bridge.py` (`StateFileWatcher` reads `state.json` → Hub; `DirectiveWriter` writes `chat`/`directives`/`plan` → `directive.json`, atomic temp+rename), `--bridge DIR` mode in `main.py`, Hub `on_directive`/`on_plan` hooks, `docs/bridge-protocol.md`. **Stage A verified**: hand-written `state.json` → real-model `directive.json` (Dakkar `attack target=vex`, strategist `expand_now` plan).
- **2026-06-26** — Built **M3 voice frontend**: `tavern/voice.py` — `PiperTTS` (say_aloud → real Piper audio, persona-voice alias map, one-voice-at-a-time via the single voice consumer), `WhisperSTT` (whisper.cpp transcribe), `VoiceInput` (push-to-talk: pynput key-hold → sounddevice 16 kHz capture → whisper → human chat, speaker-tagged). `--voice`/`--no-audio` flags; deps `pynput`/`sounddevice`/`numpy` added. 44 tests pass. Verified: Piper synth via persona alias, whisper transcribe on jfk.wav, the `say_aloud`→speak path, and `--voice` startup/teardown. (Live mic capture needs a real mic + keypress — built but not exercisable headless.)

## In progress

- **M5 — map half of the bridge.** Daemon half done; the map-side (TS→Lua reader/writer + sync) needs Reforged + World Editor + `war3_lua`, which are **user prerequisites** (none installed yet). Plan: `.claude/plans/how-can-i-start-wise-wind.md`.
- **Strategy track** — S1+S2 built. **S3** waits for M6 (AMAI hooks). **S4** is a `TAVERN_STRATEGIST_MODEL` flip once a 14B is pulled.

## Next up

1. **User prereqs for in-game test**: install/confirm Reforged + World Editor, install `war3_lua`, ready AMAI + `(4)Lost Temple`. Then **M4** (I scaffold wc3-ts-template; user runs the WE steps).
2. **M5 map half**: state-export + directive-reader in the map (synced via `BlzSendSyncData` from the start). Then **M6** AMAI fork (`commander_remote.lua`).
3. **M3 voice polish** (later): distinct voice per persona (download more Piper voices), and a real-mic test of push-to-talk end-to-end.

## Blockers / open questions

- ~~Confirm exact Ollama tags~~ — **resolved 2026-06-26**: `llama3.1:8b-instruct` is 404; canonical tags are **`llama3.1:8b`** and **`qwen2.5:7b-instruct`** (registry-verified). Code/scripts updated.

## Decisions log

- **2026-06-25** — Following design v2: `war3_lua` is the backbone bridge (not optional); AI speech renders via `BlzDisplayChatMessage` through `BlzSendSyncData` (never injected as chat); LAN-only (Battle.net disqualified); MIT license.
