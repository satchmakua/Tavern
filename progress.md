# Tavern — Progress

Living status log. Update as milestones move. See [roadmap.md](roadmap.md) for the full plan.

**Current phase:** 🚧 M0 — repo + environment
**Last updated:** 2026-06-26

---

## Milestone status

| Milestone | Status | Notes |
|---|---|---|
| Kill test | ⬜ Not started | Roleplay Dakkar vs fake state before any code |
| M0 — Repo + environment | 🚧 In progress | Repo skeleton + LICENSE + .gitignore done; toolchain not yet installed |
| M1 — One persona, chat-only | ⬜ Not started | |
| M2 — Multiple personas | ⬜ Not started | |
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

## In progress

- **M0** — repo + environment. Remaining: run `scripts/setup.ps1` to pull `llama3.1:8b-instruct` and `qwen2.5:7b-instruct`; install whisper.cpp (`base.en`) + Piper.

## Next up

1. **Kill test** — install Ollama, pull `llama3.1:8b-instruct`, roleplay Dakkar against a fake game state. This gates the entire project.
2. Finish M0 environment setup.
3. Begin M1 (`Persona`/`Hub` + `FakeState` emitter).

## Blockers / open questions

- _None yet._

## Decisions log

- **2026-06-25** — Following design v2: `war3_lua` is the backbone bridge (not optional); AI speech renders via `BlzDisplayChatMessage` through `BlzSendSyncData` (never injected as chat); LAN-only (Battle.net disqualified); MIT license.
