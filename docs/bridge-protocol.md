# Bridge protocol — daemon ⇄ WC3 map

The daemon and the map talk through two JSON files in a shared **bridge directory**
(`war3_lua` gives the map the file I/O; design §5). Both sides **write atomically**
(temp file + rename) so the reader never sees a half-written file.

Run the daemon against a bridge dir:

```bash
python -m tavern --bridge C:\path\to\bridge        # real model, runs until Ctrl-C
python -m tavern --bridge ./bridge --fake-llm      # offline, for Stage A testing
```

Daemon side: `daemon/tavern/bridge.py` (`StateFileWatcher`, `DirectiveWriter`).

---

## `state.json` — game → daemon (map writes, daemon reads)

A game-state snapshot plus any human chat typed since the last write. Same shape the
summarizers already consume (`summarize`, `summarize_team`, `summarize_outcome` in
`daemon/tavern/summarizer.py`), with one extra key `new_chat`.

```json
{
  "game_time": "03:10",
  "map": "(4) Lost Temple",
  "players": {
    "1": {"name": "you",    "race": "Human", "team": "ally",  "gold": 600, "lumber": 240, "food": "16/22", "army": ["8 footmen"], "heroes": ["Paladin L2"]},
    "3": {"name": "Dakkar", "race": "Orc",   "team": "ally",  "gold": 220, "food": "14/20", "army": ["6 grunts"], "heroes": ["Blademaster L2"]},
    "5": {"name": "Vex",    "race": "Undead","team": "enemy", "food": "18/24", "army": ["8 ghouls"], "heroes": ["Death Knight L3"]}
  },
  "events": ["enemy expanding at the eastern gold mine"],
  "new_chat": [{"speaker": "you", "text": "dakkar push their natural with me"}]
}
```

- `players` keys are WC3 player slots (1-based), matching each persona's `player_id`.
- `new_chat` is **drained every write**: the map clears it after each snapshot so the
  daemon doesn't reprocess the same line. The watcher routes each entry to
  `hub.post_chat(speaker, text, kind="human")` (which wakes any persona named in it).
- The daemon only re-reads when the file's mtime changes; a parse error (mid-write) is
  skipped and retried on the next poll (`state_poll_interval`, default 0.5 s).
- Suggested map write cadence: ~2 s.

## `directive.json` — daemon → game (daemon writes, map reads)

What the daemon wants the map to do this tick.

```json
{
  "chat": [
    {"id": 40, "persona": "Dakkar", "text": "rax done, going aggressive"},
    {"id": 41, "persona": "Dakkar", "text": "watch their nat, i'll feint north"}
  ],
  "directives": {
    "3": {"strategy": "attack_Vex", "aggression": 0.8, "target_player": "Vex"}
  },
  "plan": {
    "ally": {"phase": "mid", "intent": "attack_Vex", "objective": "pressure the natural", "target_player": "Vex", "posture": 0.8, "tech_goal": "tier2", "rationale": "..."}
  }
}
```

- `chat` is an **append log** with monotonic `id`. The map renders each line once via
  `BlzDisplayChatMessage` and remembers the highest `id` it has rendered (in a *synced*
  variable — see §6). Bounded to the last `directive_chat_limit` (default 50) entries.
- `directives` is **latest-wins per player slot**. `strategy` is already normalized to
  the controlled vocabulary (`expand_now`, `tech_up`, `defend`, `creep_more`,
  `mass_<unit>`, `attack_<player>`) by `daemon/tavern/directives.py`, so the AMAI fork
  can `switch` on a small fixed set.
- `plan` is the per-team `GamePlan` (S1/S2), exposed for debugging / future use.

## Determinism (design §6) — non-negotiable on the map side

Only the **host** reads `directive.json`. It must NOT apply changes locally. It calls
`BlzSendSyncData("TAVERN", …)`; every client catches the `SyncData` trigger and applies
the **identical** mutation (chat render + AMAI directive) on the same simulation frame.
Never branch synchronous game state on a local async file read (`GetLocalPlayer()` trap).
Build this synced path from the first line — never ship the un-synced version.
