# Bridge protocol — daemon ⇄ WC3 map

The daemon and the map talk through two files in a shared **bridge directory**. On
**Reforged** the map uses w3ts's `File` (`node_modules/w3ts/system/file` — the
Blizzard-sanctioned Preload exploit), so files must live in `Documents\Warcraft III\
CustomMapData\` and end in `.txt`. The map writes **`TavernState.txt`** and reads
**`TavernDirective.txt`**; the daemon does the mirror. Sync prefix is `TVN`.

> ✅ **Two encodings — both implemented.** The *logical* payloads are below. On disk,
> w3ts `File.write` wraps content in Preload/JASS boilerplate so `File.read` can recover it.
> The daemon speaks that exact format via `daemon/tavern/wc3codec.py` (`encode_file`/
> `decode_file`), **validated byte-identical against a real in-game `File.write`**. Pass
> `--wc3` for the real map; omit it for raw-file offline (`--fake-llm`) testing. The bridge
> dir on this machine is under **OneDrive** (`C:\Users\satch\OneDrive\Documents\Warcraft III\
> CustomMapData`).

Run the daemon against a bridge dir:

```bash
python -m tavern --bridge ./bridge --fake-llm      # offline, raw files, Stage A
# real game: --bridge "<...>\CustomMapData"  (once the WC3 codec lands)
```

See [in-game-setup.md](in-game-setup.md) for the game side. Daemon: `daemon/tavern/bridge.py`
(`StateFileWatcher`, `DirectiveWriter`). Map: `map-mod/src/bridge/*`.

---

## `TavernState.txt` — game → daemon (map writes, daemon reads)

Logical payload: a game-state snapshot as JSON (the map builds it in `state.ts`), the
shape the summarizers already consume (`summarize`, `summarize_team`, `summarize_outcome`
in `daemon/tavern/summarizer.py`). `new_chat` is added once the map captures human chat.
The current map export emits `game_time` + `players{name,race,team,gold,lumber,food}`.

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

## `TavernDirective.txt` — daemon → game (daemon writes, map reads)

Logical payload: **newline-separated, pipe-delimited lines** (the map parses these in
`directives.ts` without a Lua JSON reader):

```
CHAT|41|Dakkar|rax done, going aggressive
CHAT|42|Dakkar|watch their nat, i'll feint north
DIR|3|attack_Vex|0.8|Vex
```

- `CHAT|<id>|<persona>|<text>` — an **append log** with monotonic `id`. The map renders
  each once via `BlzDisplayChatMessage` and remembers the highest `id` seen (dedup).
- `DIR|<playerId>|<strategy>|<aggression>|<target>` — **latest-wins per slot**. `strategy`
  is pre-normalized to the controlled vocab (`expand_now`/`tech_up`/`defend`/`creep_more`/
  `mass_<unit>`/`attack_<player>`, `daemon/tavern/directives.py`) so the map can `switch`
  on a small fixed set to drive AMAI (M6).

## Determinism (design §6) — non-negotiable on the map side

Only the **host** reads `TavernDirective.txt` (`isHost()` in `main.ts`). It does NOT apply
locally — it calls `BlzSendSyncData("TVN", text)`; every client catches the SyncData event
(`sync.ts`) and runs the identical `applyDirectives` on the same frame. File reads/writes
and sync-sends are local-only (no simulation state branches on them), so host-gating them
is desync-safe. This synced path is built from the first line.
