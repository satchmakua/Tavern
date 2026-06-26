# Tavern — AI Companions for Warcraft 3

> In Warcraft 3, the Tavern is where you hire the hero companions who fight at your side. This project is a Tavern for whole players: AI teammates and opponents who chat, listen to your voice, react to the map, strategize at the macro level, and trash-talk — good-naturedly. The AI does the talking and the strategy; the existing AMAI mod does the unit micromanagement it's already good at.

Everything here is free and open source, runs offline once installed, and lives in one GitHub repo. Built for LAN play — specifically so you and Moses can fill a 4v4 or FFA lobby without needing six more humans.

This is **v2**, revised after a design review. The "What changed from v1" notes below each major section exist so anyone who saw the first draft can see the deltas; ignore them on a fresh read.

---

## 0. The one constraint that dictates the entire architecture

Warcraft 3's scripting sandbox — both Lua and the older JASS language — cannot open network sockets, cannot make HTTP requests, and during a normal game cannot read or write files. So **you cannot put an LLM call inside the map.** The language model must run in a separate process on your machine (the **Companion Daemon**), and that process must talk to the game through indirect channels.

Two directions, with very different difficulty:

- **Game → Daemon (easy).** The custom map you're running has complete authoritative game state in Lua. Getting it out to the daemon is straightforward.
- **Daemon → Game (hard).** Getting external data *into* a running game is the genuinely difficult part, and it determines your tooling choice. The honest answer is a small third-party mod (`war3_lua`). Details in §5.

Accept this and everything else falls into place.

---

## 1. Architecture

Five components in two layers. The dividing line is the WC3 sandbox boundary: above it you have full freedom in normal Python/Rust land; below it you live inside Blizzard's restrictions.

**Host side (outside the game):**

1. **Companion Daemon** — Python (asyncio). The brain. Holds one persona per AI player, talks to a local LLM via Ollama, decides what each persona says and does, and manages the bridge channels.
2. **Voice Frontend** — Python. `whisper.cpp` for speech-to-text in, Piper for text-to-speech out. Entirely decoupled from the game (it never touches the sandbox), which makes it low-risk.

**Game side (inside a custom map):**

3. **Tavern Bridge (map-side)** — TypeScript compiled to Lua, baked into a modified melee map. Reads the daemon's directive file, applies strategy changes to AMAI, renders persona chat, and exfiltrates game state + human chat back to the daemon. Plus a small DLL mod (`war3_lua`) that gives the map the file I/O it needs.
4. **Modified AMAI** — the open-source Advanced Melee AI, lightly forked so each AI player's broad strategy parameters can be nudged at runtime.

```
        HOST PC
   ┌──────────────────────────────────────────────────────────┐
   │  ┌────────────┐      ┌────────────────┐     ┌──────────┐  │
   │  │   Voice    │─────▶│   Companion    │────▶│  Ollama  │  │
   │  │  Frontend  │◀─────│     Daemon     │◀────│ (LLM)    │  │
   │  └─────┬──────┘      └───┬────────▲───┘     └──────────┘  │
   │     headset                │        │                      │
   │   (mic + phones)     directive    state +                  │
   │                        file       chat file                │
   │  ════════════════════════╪════════╪═════════════════════  │ ← sandbox
   │                          ▼        │                        │   boundary
   │  ┌─────────────────────────────────────────────────────┐  │
   │  │           Warcraft 3 Reforged (LAN host)           │  │
   │  │   custom map:  Tavern Bridge (Lua via war3_lua)    │  │
   │  │                + modified AMAI                      │  │
   │  └─────────────────────────────────────────────────────┘  │
   └──────────────────────────────────────────────────────────┘
```

> **What changed from v1:** v1 used the `War3StatsobserverSharedMemory` API as the primary read path and treated the map-side bridge as a separate channel. But that API only returns full state when you're *observing*, and you're a *player*. Since you're running a custom map anyway, the map already holds complete state — so the map is now the single source of truth, and the observer reader is demoted to an optional path for unmodified ladder maps (§5.5).

---

## 2. What you and Moses actually experience

A 4v4 starts. You're Player 1 (Human), Moses is Player 2 (Orc). The other six are Tavern Companions.

Minute one, your teammate **Dakkar** (Orc, aggressive) types: "going blademaster harass then raiders. atlas take creeps north?" (Atlas is Moses's preferred alias.) The enemy's **Vex** (Undead, smug) fires back in all-chat: "cute. we'll see how that holds up."

Minute three, Moses says aloud — picked up by his headset mic — "Dakkar, push their natural with me." The daemon transcribes it, routes it to Dakkar with Moses tagged as the speaker, and Dakkar replies in chat: "on it, give me 30s for my second hero." Behind the scenes Dakkar's directive shifts AMAI toward early aggression with its rally point on the enemy expansion.

Minute twelve, your opponent **Grollum** (Night Elf, dry) types: "whoever told you to skip beastmaster should be tried at the hague."

That's the whole product. Not a benchmark — a way to play your favorite mode with teammates and rivals made of language.

---

## 3. The Voice Frontend (lowest risk, build it to feel the magic early)

Voice in and out is entirely host-side and never touches the game sandbox. The only game dependency is that the daemon needs game *context* to respond well, and that arrives via the state exfil. So you can build and tune the whole voice loop with the game closed.

**Speech in.** `whisper.cpp` with the `base.en` model: tiny footprint, near-realtime on CPU, accurate enough for casual chatter, with `silero-vad` for voice-activity detection (ships with whisper.cpp). The frontend listens, transcribes, and pushes utterances onto a queue tagged by speaker.

**Speaker routing without a diarization model.** With two humans in the room, route by *device*: each human on a separate microphone, each mic its own audio device, utterances tagged by device. "Dakkar, push" from your mic goes to Dakkar and references you; the same from Moses's mic references Atlas. Moses already runs a separate mic for his assistive controls, so this is natural.

**Push-to-talk, and why it's mandatory at first.** Always-listening sounds magical and fails the instant the dog barks. Worse — and this is the real reason — **open mics plus speaker output create a feedback loop: the AI's own TTS gets picked up and transcribed as if a human said it.** Solve it with (a) push-to-talk so the mic only captures while a key/button is held, and (b) **headsets, not room speakers**, so the AI voices play into headphones near the ear rather than back into the mics. For Moses, a button on his rig is the push-to-talk; a headset with a close mic kills the feedback path. You can graduate to a wake-word always-on mode later, but start gated.

**Speech out.** Piper is the best free TTS in 2026: tiny, fast, dozens of voices. Each persona gets a distinct voice (Dakkar deeper and gruffer, Vex cooler and clipped). The frontend keeps a per-persona TTS queue. Use voice *sparingly* — constant chatter gets old. In the persona prompts, make speaking aloud rare ("only speak aloud on something dramatic; otherwise type in chat") and prefer chat for routine lines. Hard rule: only one persona speaks aloud at a time across all of them, to avoid an unintelligible pile-up.

> **What changed from v1:** added the feedback-loop hazard explicitly (it's the thing that silently breaks always-on voice), and tied the headset requirement to it rather than treating headphones as an afterthought.

---

## 4. The LLM brain

Hardware determines the model. Three tiers, in order of preference for a starting point:

- **Llama 3.1 8B Instruct** via Ollama — runs comfortably on an 8 GB+ VRAM GPU (your RTX 5060 has the room). Good for chat, jokes, and strategy. ~1–3 s per short response.
- **Qwen 2.5 7B Instruct** — strong backup, often better at structured JSON output, which matters for the directive channel.
- **Gemma 3 4B / Phi-3 Mini** — lower latency, less depth. Use for noisier personas (especially enemy banter) that don't need to make real decisions.

Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`. Each persona turn returns a single JSON object:

```json
{
  "say_in_chat": "rax done, going treants",
  "say_aloud": null,
  "directive": {"strategy": "expand_then_tech", "aggression": 0.3, "target_player": null},
  "thinking": "teammate just lost their altar, hold the push"
}
```

`thinking` is logged for debugging and read by nothing. The daemon acts on the rest.

**Personas.** One short system prompt per AI player — name, race lean, temperament, constraints. Example (the aggressive Orc):

> You are Dakkar, an AI player in a 4v4 Warcraft 3 game. You play Orc, favor early Blademaster aggression, and trash-talk in a friendly way. You're teamed with the human players God and Atlas. Speak casually, lowercase, like real in-game chat — never more than two short sentences. You'll see the game state every few seconds and sometimes things teammates or opponents just said. Decide whether to chat, whether to speak aloud (rare — only on something dramatic), and what coarse strategic directive to issue.

Keep them short; long prompts leak into every response and burn context. Six to twelve personas, one file each in `/personas`, mixing races and tempers.

**The directive vocabulary — deliberately small.** The daemon does not move units. It picks coarse intents and the Bridge translates them into AMAI parameter nudges. Start minimal; expanding later is easy, debugging twenty knobs at once is not.

| Directive | Bridge tells AMAI to… |
|---|---|
| `expand_now` | drop an expansion within ~60 s |
| `tech_up` | prioritize the next tier over army |
| `mass_<unit>` | bias production toward a unit |
| `attack_<player>` | aim attack waves at a player (or lure via a dummy target) |
| `defend` | pull army home, hold base |
| `creep_more` | prioritize creeping for hero XP |
| `aggression=<0..1>` | dial AMAI's existing aggression knob |

---

## 5. The Bridge — getting data across the sandbox boundary

This is where most of the engineering time goes and where realistic expectations matter most.

### 5.1 The backbone: `war3_lua` file channel

The cleanest bidirectional channel uses **`Ev3nt/war3_lua`**, a third-party mod that runs Lua at the JASS level and unlocks capabilities the official sandbox withholds — including file I/O. With it:

- **Daemon → Game:** the daemon writes a small JSON `directive file`; the map reads it (poll on a timer, or on `war3_lua`'s file hooks). Millisecond-fast, focus-independent.
- **Game → Daemon:** the map writes a `state file` (compact game-state snapshot + any new human chat); the daemon's file-watcher picks it up.

Cost: `war3_lua` is a binary mod, it can break on game patches, and it disqualifies Battle.net — you must play LAN. For this project that's not a sacrifice; LAN is what you want for couch co-op with Moses.

### 5.2 Render AI speech in the map — never inject it as chat

The AI's spoken lines are **not** typed into the game's chat input. The map reads them from the directive file and renders them itself via `BlzDisplayChatMessage`, attributed to the persona's name. This avoids chat-spam entirely and gives clean attribution. (Confirmed: `BlzDisplayChatMessage` is a Reforged native.)

```typescript
// On reading a directive that contains persona speech:
BlzDisplayChatMessage(GetLocalPlayer(), 0, "Dakkar: rax done, going treants");
```

(See §6 on why this specific call must be reached via a synced path, not a raw local read.)

### 5.3 Applying directives to AMAI

A small forked-AMAI module — `commander_remote.lua` — exposes:

```
AMAI.setStrategy(player, "expand_now")
AMAI.setStrategy(player, "attack_p5")
AMAI.setAggression(player, 0.7)
AMAI.setTechBias(player, "tier2")
```

Each flips an existing AMAI internal global that AMAI's own decision loop already reads. AMAI's source is well-commented; the Hive Workshop "JASS Campaign AI 2.0" thread maps the relevant variables. Total addition to AMAI is on the order of 200 lines.

### 5.4 The map and AMAI fork

You are not building a melee map from scratch. Take a standard map (e.g. (4)Lost Temple), open it in the **World Editor** (ships with Reforged), install **AMAI** (`SMUnlimited/AMAI`) into it, confirm vanilla AMAI works, then add the Bridge scripts.

Tooling for the Bridge: **TypeScript-to-Lua via `cipherxof/wc3-ts-template`** — type-checked, real testing, real package management, and it matches your background and toolchain preferences. (WurstScript is the alternative; both compile to Lua. TypeScript is the recommended pick here.)

### 5.5 The no-DLL fallback channels (for reference)

If you ever need to run without `war3_lua`:

- **Game → Daemon without a DLL:** abuse the `Preload`/`PreloadGenEnd` mechanism to write arbitrary strings to a file on disk that the game *does* produce during normal play; the daemon watches that file. Cleaner than parsing memory.
- **Daemon → Game without a DLL:** the only option is simulated input (AutoHotkey / `pywinauto` typing into the window). **This has a real flaw:** any command message is visible in the game chat to you and Moses, and standard WC3 can't reliably swallow a chat line after it's sent, so it spams the chat. Use this only as a temporary scaffold during early integration, never as the destination.

The observer shared-memory reader from v1 also survives here as an option, but only for *unmodified* maps where you can't add a Bridge — and it requires a dedicated observer client because, as a player, you don't get full data.

> **What changed from v1:** `war3_lua` is promoted from optional-milestone-7 to the backbone. AI speech now renders via `BlzDisplayChatMessage` instead of being injected, eliminating the chat-spam problem. AutoHotkey is correctly demoted to a scaffold with its flaw named.

---

## 6. Determinism and desync — read this before you write the Bridge

Warcraft 3 is **lockstep-deterministic**: every client runs the identical simulation and they exchange only player inputs. AMAI executes *inside that simulation on every client*. If the host reads the directive file and mutates AI state **on the host only**, the host's simulation diverges from everyone else's, and the game drops players with a mystery "desync" disconnect. This is the single most likely thing to make the project seem cursed.

**The required pattern:**

1. Only one client (the host) reads the external directive file via `war3_lua`.
2. The host does **not** apply it directly. It calls `BlzSendSyncData` to broadcast the directive to all clients.
3. Every client (host included) catches the sync via a `SyncData` trigger event and applies the *identical* mutation — strategy change, and the `BlzDisplayChatMessage` render — on the same simulation frame.

That keeps all simulations identical. `BlzSendSyncData` exists for exactly this. The corollary: never branch the synchronous game state on anything read locally and asynchronously (the classic `GetLocalPlayer()` trap) — route everything through the sync.

```
host war3_lua reads directive file
        │
        ▼
host: BlzSendSyncData("TAVERN", payload)
        │   (network)
        ▼
ALL clients: SyncData trigger fires
        │
        ▼
ALL clients: apply strategy + BlzDisplayChatMessage  (identical, same frame)
```

This applies in your LAN game even though only you and Moses are human — both human clients, and any observer client, must stay in lockstep.

> **What changed from v1:** this section did not exist. It's non-optional.

---

## 7. Throughput, latency, and topology

Seven personas each firing an 8B inference, serialized on one GPU shared with the game, is 7–20+ seconds per full round and can hitch your frames mid-inference. "Reacts in 3 seconds" does not survive that naively. Four mitigations, in order of impact:

1. **Hard gating — most personas say nothing most ticks.** A persona only calls the LLM when (a) a human or another persona addresses it by name, (b) a major event happens near it (hero death, base lost, expansion finished), or (c) a randomized idle-banter timer fires. At any instant usually one or two personas are inferring, not seven.
2. **Priority queue.** An @-mention jumps ahead of idle banter. Your teammates' responsiveness is prioritized over enemy chatter.
3. **Tiered models.** Run the 8B only for the personas currently in focus (your teammates, the opponent you're fighting). Noisier enemy personas run a 4B model.
4. **Second machine (the real fix if you have one).** On a LAN you can run Ollama on a separate box and point the daemon's HTTP client at it over the network. That removes GPU contention with the game entirely and is the recommended topology if a second GPU machine is available. If not, cap Ollama's GPU layers or fall back to CPU inference for background personas so the game stays smooth.

**Loop damping for AI↔AI.** If persona A's chat triggers B's tick which re-triggers A, you get runaway back-and-forth. Rules: a persona responds to *another AI's* message at most once, and any AI-to-AI exchange has a hard turn cap (e.g. three) before both fall silent. Plus the duplicate-response arbiter: if two personas would react to the same event, randomize who speaks and the other stays quiet.

**Latency masking.** Keep a handful of canned string responses for very common moments ("gg wp", "nice creep route", "rax done") and use them when the LLM is mid-flight, so the persona isn't visibly silent while it thinks. The model only speaks when it has something genuinely contextual to add.

> **What changed from v1:** the per-GPU throughput math is now explicit, gating/priority/tiering/second-machine are spelled out as the answer, and AI↔AI runaway loop damping is added.

---

## 8. AMAI: influence, not puppetry — and the expectation gap

The daemon **influences** AMAI; it does not puppet it. AMAI runs its own competent baseline (build orders, army management, micro), and directives nudge its broad tendencies: aggression, attack target, tech tier, rough composition, expand timing. This split is deliberate — reinventing competent RTS AI is a multi-month effort you don't want, and AMAI is genuinely good at the micro the LLM can't do.

**Be honest about the gap.** AMAI's build orders are largely fixed per script, so the daemon can reliably steer *coarse* behavior but probably can't dictate a *precise* opening without deep source surgery. Practically: a persona may **say** "Blademaster harass into Raiders" while AMAI executes generic early aggression. For a fun game with your brother that's fine — the talk carries most of the experience — but the doc names it rather than pretending the AI's actions are as specific as its words. Closing that gap (making said-strategy and done-strategy converge) is the long-tail work, not a v1 requirement.

If a directive has no clean AMAI hook, two fallbacks: AMAI accepts player chat commands for many behaviors (drive those through the synced channel), or spawn an invisible high-priority dummy unit near the desired target to lure AMAI's attack logic.

> **What changed from v1:** the said-vs-done expectation gap is now stated outright, and the AMAI-controllability risk is elevated (it's the riskiest single integration point; see §11).

---

## 9. The Companion Daemon (host-side glue)

A single Python asyncio process:

- One coroutine per persona, each with its own state, conversation history, and rate limit.
- A file-watcher on the map's state file (game state + new human chat).
- A queue subscriber to the Voice Frontend for transcribed human speech, tagged by speaker.
- A directive-file writer the map reads.
- A bounded shared chat history so personas react to each other and to humans.
- A **summarizer** that reduces the raw state snapshot to ~15–20 lines of natural language scoped to one player's perspective before feeding the LLM. This is straight from the TextStarCraft II approach and is essential — feeding raw state every tick burns context and confuses the model.

```python
async def persona_loop(persona, hub):
    while True:
        await persona.wake.wait()                       # gated: name-mention, event, or idle timer
        summary = summarize(hub.latest_state, persona.player_id)
        history = hub.recent_chat(limit=10)
        out = await ask(persona.system_prompt, summary, history)   # Ollama, JSON out
        if out["say_in_chat"]:
            await hub.queue_directive(persona, chat=out["say_in_chat"])
        if out["say_aloud"]:
            await hub.voice_out.put((persona, out["say_aloud"]))
        if out["directive"]:
            await hub.queue_directive(persona, strategy=out["directive"])
```

`queue_directive` batches chat-render and strategy into the directive file the host reads and *syncs* (§6). Cadence: idle-banter timer ~30 s jittered per persona; name-mentions wake immediately; throttle any persona to at most one chat line per ~6 s.

---

## 10. Build sequence

Build each piece on a working previous piece. Don't parallelize until confident.

**M0 — Repo + environment (evening).** Create repo `tavern`, MIT. Layout: `/daemon` (Python), `/map-mod` (TypeScript + AMAI fork), `/personas` (YAML), `/docs`, `/scripts`. Install Ollama; pull `llama3.1:8b-instruct` and `qwen2.5:7b-instruct`; confirm both at `:11434`. Install whisper.cpp (`base.en`) and Piper; confirm transcription and synthesis.

**M1 — One persona, chat-only, no game (week 1).** Build `Persona`/`Hub`. Write a `FakeState` emitter that plays scripted game events from a JSON file on a timer. Wire Ollama. Tune one persona until it feels alive and not annoying. **This is the highest-leverage, zero-cost work in the project — spend real time here.** Add the JSON output schema + validation.

**M2 — Multiple personas in conversation (week 2).** Four persona coroutines, shared chat history, @-mention immediate-wake, duplicate-response arbiter, AI↔AI turn cap. Tune the trash-talk dial per persona.

**M3 — Voice in and out (week 3).** Voice Frontend with push-to-talk (`pynput`), per-device speaker tagging, `say_aloud` end-to-end with per-persona Piper voices, one-voice-at-a-time cap. Confirm headset setup kills the feedback loop. Confirm Moses can hear AI voices through his headphones.

**M4 — Map + AMAI baseline (week 4).** Copy (4)Lost Temple, install AMAI, confirm vanilla AMAI plays. Stand up `wc3-ts-template`; get a "hello world" trigger compiling to Lua and running. (This step alone is ~a day; AMAI's installer has quirks.)

**M5 — `war3_lua` file bridge, one direction at a time (weeks 5–6).** Install `war3_lua`. First **Game → Daemon**: map writes the state file, daemon watches it — confirm chat and resources appear in daemon logs. Then **Daemon → Game**: daemon writes a directive file, map reads it. Render a test persona line via `BlzDisplayChatMessage` — but route it through `BlzSendSyncData` from the start so you never build the un-synced version.

**M6 — Sync hardening + AMAI hooks (week 7).** Implement the full §6 pattern: host reads file → `BlzSendSyncData` → all clients apply identically. Test a 1v1 vs one Companion across two machines on the LAN and confirm **no desync**. Fork AMAI, add `commander_remote.lua`, wire `applyDirective`. Confirm directives visibly change AMAI behavior (watch what it builds and where it attacks); bump magnitudes if the changes are too subtle.

**M7 — Full 4v4, mixed voice + chat (weeks 8–9).** Seven personas (three allied AI, four enemy AI), you and Moses human, LAN. Tune the chatbot pile-on at scale (cadences, arbitration, tiered models). Stress-test GPU contention; move Ollama to a second machine if it hitches. Confirm seven TTS queues behave (sequential per persona, parallel across).

**M8 — Polish + packaging (week 10+).** Expand to 8–12 personas with distinct voices. A one-click launcher (a PowerShell script is plenty) that starts Ollama, the daemon, and the Voice Frontend. Structured logging of every LLM call, directive, sync, and event — you'll be debugging emergent behavior for months and this saves your sanity. A README a stranger could follow, with an honest minimum-spec section.

> **What changed from v1:** the observer-reader milestone is gone (folded into optional §5.5); `war3_lua` is now the M5 backbone instead of an optional M7; a dedicated sync-hardening milestone (M6) is added; voice moved earlier since it's decoupled and low-risk.

---

## 11. Risks, with honest severities

**AMAI doesn't shift behavior much when you flip its globals — HIGH.** The riskiest single integration point. Read AMAI's source carefully *before* committing to a directive vocabulary. Fallbacks: AMAI's own chat-command surface (driven through the synced channel) and the dummy-target lure for attack redirection. Expect to bump directive magnitudes well past your first guess.

**Desync from un-synced state mutation — HIGH if §6 is ignored, near-zero if followed.** Build the synced path from M5; never ship the un-synced version even as a test.

**LLM latency / throughput makes chat feel laggy — HIGH on first build.** Gating + priority + tiered models + canned-line masking; second machine if available.

**Audio feedback loop — HIGH without headsets.** Push-to-talk + headsets, not room speakers. Non-negotiable for always-on later.

**Reforged patch breaks `war3_lua` — MODERATE, every few months.** Pin a known-good Reforged build in your dev environment; update `war3_lua` from upstream when it breaks. The `Preload` exploit (§5.5) is a no-DLL fallback for the read direction if `war3_lua` lags a patch.

**Said-strategy vs done-strategy gap — MODERATE, by design.** Lower expectations: the AI talks a more specific game than it plays. Acceptable for v1; converging them is long-tail work.

**Scope creep — CERTAIN.** Park voice cloning, vision-based micro, and cross-game persona memory in `FUTURE.md`. Revisit only after one good 4v4 has actually been played.

**ToS / modding gray area — LOW for private LAN use.** WC3 modding is broadly tolerated, but DLL-level mods are grayer. For private LAN games with your brother the practical risk is negligible. Don't ship it as a Battle.net product; keep it LAN-private and unofficial. Distribute your code, not Blizzard assets.

---

## 12. Costs, hardware, licensing

**Money: zero.** WC3 Reforged (you own it), Ollama (MIT), Llama 3.1 (community license, effectively free under 700M MAU), Qwen 2.5 (Apache 2.0), whisper.cpp (MIT), Piper (MIT), AMAI (GPL-style OSS), `wc3-ts-template` (MIT), `war3_lua` (OSS), VB-Cable (free for personal use).

**Hardware.** Your RTX 5060 laptop runs the 8B model with room to spare and can run it alongside Reforged (which is light by 2026 standards, though heavier than classic WC3). 16 GB RAM minimum, 32 GB comfortable. A second mic + headset for Moses. **Optional but recommended: a second LAN machine to host Ollama**, removing all GPU contention.

**License.** MIT for your code, crediting AMAI and the underlying tools.

---

## 13. Definition of done (v1)

A 4v4 LAN match — you, Moses, six Companions — where: each AI has a name, race, voice, and consistent personality; AIs chat unprompted and in response to teammates and opponents; you and Moses address teammates by name and get a reply in chat or voice within ~3 s; AIs occasionally speak aloud; AI strategy visibly shifts on directives (when an AI says it's going aggressive, AMAI gets more aggressive); the whole thing runs offline with no paid APIs and **no desyncs**; and it's one GitHub repo with a README another competent engineer could follow.

Hard but realistic: ~10–12 weeks of evenings and weekends for a competent solo engineer with prior context on the pieces — which is to say, you.

---

## 14. The very first thing to do — the kill test

Before any code: install Ollama, pull `llama3.1:8b-instruct`, and run a five-minute roleplay where you tell it to be "Dakkar, an aggressive Orc player in Warcraft 3" and you describe a fake game state to it in chat.

If Dakkar feels in-character, contextual, and not dull, the whole thesis holds and the rest is engineering. If it feels flat, switch to `qwen2.5:7b-instruct` and retry. If both feel flat on your hardware, **stop** — the LLM-as-RTS-player thesis is what makes Tavern work, and no amount of bridge engineering rescues a brain that isn't fun to talk to.

If it feels good, open your editor, create `tavern`, and start on M0.
