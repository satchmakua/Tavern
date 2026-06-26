# /map-mod — Tavern Bridge + AMAI fork (TypeScript → Lua)

Game-side, inside a modified melee map. See [design §5](../tavern-design.md), [§6](../tavern-design.md), and [§8](../tavern-design.md).

Built with [`cipherxof/wc3-ts-template`](https://github.com/cipherxof/wc3-ts-template) (TypeScript-to-Lua, type-checked). Base map: `(4)Lost Temple` opened in the Reforged World Editor, with [AMAI](https://github.com/SMUnlimited/AMAI) installed.

**Tavern Bridge** reads the daemon's directive file and writes the state snapshot via the Preload-based **FileIO** library (`FileIO.Save`/`FileIO.Load`, files in `Documents\Warcraft III\CustomMapData\Tavern\`), applies strategy changes to AMAI, and renders persona chat with `BlzDisplayChatMessage`. **Note:** the design's `war3_lua` is classic-WC3-only (1.24–1.28) and is **not** used on Reforged — FileIO replaces it. See [docs/in-game-setup.md](../docs/in-game-setup.md).

**Critical — determinism (§6):** only the host reads the directive file. It must **not** apply changes directly. It calls `BlzSendSyncData`; every client catches the `SyncData` trigger and applies the *identical* mutation on the same simulation frame. Never branch synchronous game state on a local async read (the `GetLocalPlayer()` trap). Build the synced path from day one — never ship the un-synced version, even as a test.

**AMAI fork** — `commander_remote.lua` (~200 lines) exposes `setStrategy`/`setAggression`/`setTechBias`, each flipping an existing AMAI global its decision loop already reads.

**Bridge wire format is fixed and the daemon half is built** — the map writes `state.json` and reads `directive.json` per [docs/bridge-protocol.md](../docs/bridge-protocol.md). Daemon side: `daemon/tavern/bridge.py`, exercised via `python -m tavern --bridge <dir>` (Stage A passing). The map's state-export targets the schema the summarizers already consume; `directive.directives[<slot>].strategy` is pre-normalized to the controlled vocab the AMAI fork switches on.

_Empty — populated starting at M4 (needs Reforged + World Editor)._
