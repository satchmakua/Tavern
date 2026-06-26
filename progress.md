# Tavern — Progress

Living status log. Update as milestones move. See [roadmap.md](roadmap.md) for the full plan.

**Current phase:** 🚧 M1/M2 — daemon code complete, tuning pending real LLM
**Last updated:** 2026-06-26

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| Kill test | ⬜ Not started | Roleplay Dakkar vs fake state before any code |
| M0 — Repo + environment | 🚧 In progress | Repo skeleton + LICENSE + .gitignore done; toolchain not yet installed |
| M1 — One persona, chat-only | 🚧 In progress | Daemon built & `--fake-llm` verified end-to-end (17 tests pass); persona tuning pending real Ollama |
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

## In progress

- **M0** — environment: run `scripts/setup.ps1` to pull `llama3.1:8b-instruct` and `qwen2.5:7b-instruct`; install whisper.cpp (`base.en`) + Piper.
- **M1/M2** — code complete; remaining is **persona tuning**, which needs a real model (the high-leverage "make Dakkar feel alive" work from the design).

## Next up

1. **Kill test** — install Ollama, pull `llama3.1:8b-instruct`, then `python -m tavern --persona Dakkar` (no `--fake-llm`) and tune until it feels alive. This gates the project.
2. Finish M0 (whisper.cpp + Piper) and tune the four personas against the real model.
3. **M3 — Voice frontend** (`/daemon` voice in/out): whisper.cpp + Piper, push-to-talk, per-device speaker tagging, one-voice-at-a-time. This is the next *buildable* milestone without the game.

## Blockers / open questions

- Confirm the exact Ollama tags exist (`llama3.1:8b-instruct` / `qwen2.5:7b-instruct` vs `llama3.1:8b` / `qwen2.5:7b`). `setup.ps1`/`--model` can override.

## Decisions log

- **2026-06-25** — Following design v2: `war3_lua` is the backbone bridge (not optional); AI speech renders via `BlzDisplayChatMessage` through `BlzSendSyncData` (never injected as chat); LAN-only (Battle.net disqualified); MIT license.
