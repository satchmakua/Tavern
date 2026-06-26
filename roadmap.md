# Tavern — Roadmap

The build sequence from [tavern-design.md](tavern-design.md) §10. **Each piece is built on a working previous piece — do not parallelize until confident.** Estimate: ~10–12 weeks of evenings/weekends for a competent solo engineer.

Beyond design §10, the **[Strategy track (S1–S4)](#strategy-track-s1s4--making-the-agents-out-strategize-scripted-ai)** is first-class work (not parked): it's what makes the agents' *decisions* genuinely smarter and more creative than scripted AI, closing design §8's said-vs-done gap.

Track live status in [progress.md](progress.md).

---

## Kill test (before any code)

Install Ollama, pull `llama3.1:8b`, run a five-minute roleplay as "Dakkar, an aggressive Orc player in Warcraft 3" against a fake game state you describe in chat.

- If Dakkar feels in-character, contextual, and not dull → the thesis holds, proceed to M0.
- If flat → try `qwen2.5:7b-instruct`. If both feel flat on this hardware → **stop.** No bridge engineering rescues a brain that isn't fun to talk to.

---

## Milestones

### M0 — Repo + environment *(evening)*
Create repo, MIT license. Scaffold layout: `/daemon`, `/map-mod`, `/personas`, `/docs`, `/scripts`. Install Ollama; pull `llama3.1:8b` and `qwen2.5:7b-instruct`; confirm both at `:11434`. Install whisper.cpp (`base.en`) and Piper; confirm transcription and synthesis.

### M1 — One persona, chat-only, no game *(week 1)*
Build `Persona`/`Hub`. Write a `FakeState` emitter that replays scripted game events from a JSON file on a timer. Wire Ollama. Add the JSON output schema + validation. **Tune one persona until it feels alive and not annoying — highest-leverage, zero-cost work in the project. Spend real time here.**

### M2 — Multiple personas in conversation *(week 2)*
Four persona coroutines, shared chat history, @-mention immediate-wake, duplicate-response arbiter, AI↔AI turn cap. Tune the trash-talk dial per persona.

### M3 — Voice in and out *(week 3)*
Voice Frontend: push-to-talk (`pynput`), per-device speaker tagging, `say_aloud` end-to-end with per-persona Piper voices, one-voice-at-a-time cap. Confirm headsets kill the feedback loop and that Moses can hear AI voices through his headphones.

### M4 — Map + AMAI baseline *(week 4)*
Copy `(4)Lost Temple`, install AMAI, confirm vanilla AMAI plays. Stand up `wc3-ts-template`; get a "hello world" trigger compiling to Lua and running. (~a day on its own; AMAI's installer has quirks.)

### M5 — `war3_lua` file bridge, one direction at a time *(weeks 5–6)*
Install `war3_lua`. First **Game → Daemon**: map writes state file, daemon watches it — confirm chat and resources appear in daemon logs. Then **Daemon → Game**: daemon writes directive file, map reads it. Render a test persona line via `BlzDisplayChatMessage` — **routed through `BlzSendSyncData` from the start** so the un-synced version is never built.

### M6 — Sync hardening + AMAI hooks *(week 7)*
Implement the full §6 pattern: host reads file → `BlzSendSyncData` → all clients apply identically. Test 1v1 vs one Companion across two LAN machines, confirm **no desync**. Fork AMAI, add `commander_remote.lua`, wire `applyDirective`. Confirm directives visibly change AMAI behavior; bump magnitudes if too subtle.

### M7 — Full 4v4, mixed voice + chat *(weeks 8–9)*
Seven personas (three allied AI, four enemy AI), you and Moses human, LAN. Tune chatbot pile-on at scale (cadences, arbitration, tiered models). Stress-test GPU contention; move Ollama to a second machine if it hitches. Confirm seven TTS queues behave (sequential per persona, parallel across).

### M8 — Polish + packaging *(week 10+)*
Expand to 8–12 personas with distinct voices. One-click launcher (PowerShell is plenty) that starts Ollama, daemon, and Voice Frontend. Structured logging of every LLM call, directive, sync, and event. A README a stranger could follow, with an honest minimum-spec section.

---

## Strategy track (S1–S4) — making the agents out-strategize scripted AI

The M-track makes the agents *talk* strategy and adapt/coordinate. **This track makes their decisions genuinely better and more creative than AMAI** — the core ambition. It's daemon-side, so build and verify it against `FakeState` before the bridge exists.

> **Why this is its own track:** the current single-shot 8B-per-tick design produces strategy *talk* but mediocre strategy *decisions* (observed: Dakkar pinning `aggression=1.0` every turn with free-form intents). Clearing the "smarter than AMAI" bar takes a deliberate planner, grounding, a wider control surface, and a stronger model — below.

**Sequencing:** **S1–S2 before M6** (the brain should be good before it drives AMAI). **S3 co-designed with M6** (the control surface *is* what a plan can express into AMAI). **S4 around M7** (when GPU/topology is already being sorted).

### S1 — Strategist loop (deliberate planner, separate from banter)
Split the macro brain from the chatter. A per-team **Strategist** holds a persistent `GamePlan` (phase, primary objective, target, posture, tech goal, rationale), reads a fuller team-scoped state on a slower cadence (~20–30 s) plus event wakes, and revises the plan with explicit reasoning. Personas derive their chat + directives *from* the team plan instead of reinventing strategy every tick. Verify against `FakeState`; local 8B to start. This is the single biggest lever and matches the TextStarCraft II pattern design §9 cites.

### S2 — Grounding + feedback + controlled vocabulary
Give the strategist RTS knowledge (build orders, matchup heuristics, timing windows) via system prompt + light retrieval, and feed back the outcome of prior directives ("last push failed, they held with towers") so it adapts instead of vibing. Constrain directives to the controlled vocabulary (§4) with validation + repair. Kills the `aggression=1.0`-every-turn failure mode.

### S3 — Widen the control surface *(co-designed with M6)*
Expand what a plan can express into the game: a richer directive set, AMAI chat-command passthrough, and dummy-target lures for attack redirection. The bridge from "good plan" to "it happens on the map." Co-evolves with the M6 AMAI hooks.

### S4 — Stronger strategist model / topology
Move the strategist to a 14B/32B (or the second-machine Ollama in §7); keep banter on 8B/4B. The 8B is the ceiling on decision quality — this is where it climbs. Measure the uplift (better calls, not just longer ones).

---

## Definition of done (v1)

A 4v4 LAN match — you, Moses, six Companions — where:
- each AI has a name, race, voice, and consistent personality;
- AIs chat unprompted and in response to teammates and opponents;
- you and Moses address teammates by name and get a reply (chat or voice) within ~3 s;
- AIs occasionally speak aloud;
- strategy is more than coarse: a per-team strategist holds a **game plan**, adapts to the human's calls and the opponent's play, revises mid-game, and visibly steers AMAI (says aggressive → AMAI gets more aggressive), with said- and done-strategy broadly converging;
- it runs fully offline, no paid APIs, **no desyncs**;
- it's one GitHub repo with a README another competent engineer could follow.

---

## Parked — revisit only after one good 4v4 has been played (FUTURE)

Scope creep is *certain*; park it here rather than letting it derail v1.

- Voice cloning for personas
- Vision-based micro (LLM driving units directly)
- Cross-game persona memory
- Wake-word always-on voice (replacing push-to-talk)
- Full said/done convergence at the level of *precise openings* (deep AMAI build-order surgery) — the Strategy track (S1–S4) closes the **macro** gap; pixel-precise build execution stays long-tail
- Battle.net / non-LAN support (currently disqualified by `war3_lua`)
- Observer shared-memory reader for unmodified ladder maps (design §5.5)

---

## Known high-severity risks (design §11)

| Risk | Severity | Mitigation |
|---|---|---|
| AMAI doesn't shift behavior when globals flip | HIGH | Read AMAI source before fixing directive vocab; use chat-command surface + dummy-target lure; bump magnitudes |
| Desync from un-synced state mutation | HIGH if §6 ignored | Build the synced path from M5; never ship un-synced, even as a test |
| LLM latency makes chat feel laggy | HIGH on first build | Gating + priority queue + tiered models + canned-line masking; second machine |
| Audio feedback loop | HIGH without headsets | Push-to-talk + headsets, never room speakers |
| Reforged patch breaks `war3_lua` | MODERATE | Pin a known-good Reforged build; `Preload` exploit as no-DLL read fallback |
