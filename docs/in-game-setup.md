# Tavern — In-game setup (Warcraft III Reforged)

Your explicit, do-this-exactly checklist to get the game ready for the bridge. Three
short stages (~30–40 min total). After you finish them and report a couple of paths
back, I take over the code (scaffold the map project + write the bridge).

> **Correction to the design (important):** the design doc named `war3_lua` for file
> I/O, but that tool only supports **classic** WC3 (1.24–1.28), **not Reforged**. On
> Reforged we instead use the community **FileIO** library (the Preload trick) to
> read/write text files under `Documents\Warcraft III\CustomMapData\`. Upside: **no
> DLL mod, no binary injection** — simpler and lower-risk. You don't install anything
> for FileIO; it's a Lua snippet I bundle into the map.

## Already done ✅
- **Reforged** installed at `C:\Program Files (x86)\Warcraft III\` (exe paths confirmed).
- **Node v24**, **npm 11**, **git 2.54** — present, so the TypeScript→Lua toolchain is ready.
- **Local Files enabled** — I set `HKCU\Software\Blizzard Entertainment\Warcraft III` →
  `Allow Local Files = 1` (verified). *(Stage 2 below is done.)*
- **AMAI 3.6.0 downloaded + extracted** to `tools/amai/`, ready to install.
- Daemon side of the bridge is built and tested (writes `directive.json`, reads `state.json`).
- **Your WC3 data lives in OneDrive:** `C:\Users\satch\OneDrive\Documents\Warcraft III\`
  (Documents is redirected). So the **bridge directory** will be
  `…\OneDrive\Documents\Warcraft III\CustomMapData\Tavern\`. *(Watch item: OneDrive may
  sync/lock the rapidly-updated bridge files — we may pause sync on that folder.)*

> **Note:** I first tried AMAI's *local-mod* method (scripts in `_retail_\Scripts\`), but
> Reforged **2.0.4** doesn't honor that global override (no AMAI dialog appeared). AMAI 3.6.0
> *does* support 2.0.4 — so we use the reliable **per-map install** below, which is what our
> bridge map needs anyway. (Those inert `_retail_\Scripts\` files are harmless; delete the
> folder anytime.)

---

## The one step left for you — make a base map  *(~3 min in the World Editor)*

This same map becomes the base for our bridge, so it's not throwaway work.

1. Open the **World Editor** (`…\_retail_\x86_64\World Editor.exe`).
2. **File → Open Map…** → open the built-in **`(4) Lost Temple`**.
3. **File → Save Map As…** → save to **`C:\Tavern\maps\LostTemple.w3x`**
   (create the `C:\Tavern\maps\` folder; keep it OUT of OneDrive to avoid sync locks).
4. **➡️ Tell me when it's saved** (or paste the exact path). Then **I** run the AMAI
   per-map installer on it (`InstallREFORGEDToMap.bat "…LostTemple.w3x" 0` — Commander
   off, since Tavern is our commander) and hand it back.

### Then you verify AMAI *(5 min)*
Warcraft III → **Single Player → Custom Game** → load your AMAI'd `LostTemple.w3x` → add a
**Computer** opponent → **Start**. A brief **language dialog** at the start = AMAI loaded;
then watch it **expand, tech, and attack** like a real player. Report **"AMAI works."**

---

## After your play-test — what I do (no action from you)

- Scaffold `map-mod/` from **wc3-ts-template** (`npm install`; set `config.json` →
  `gameExecutable` = your `Warcraft III.exe`). Confirmed prereqs: Node + WC3 1.31+.
- Bundle **FileIO** + write the **Tavern Bridge** (TypeScript→Lua):
  - **Game → Daemon:** every ~2 s, `FileIO.Save` a `state.json`-shaped snapshot + new
    human chat into `CustomMapData\Tavern\`.
  - **Daemon → Game:** host reads `directive.json` via `FileIO.Load`, then **`BlzSendSyncData`**
    → every client renders the line with `BlzDisplayChatMessage` and applies the AMAI
    directive on the same frame (design §6 — synced from the first line).
- **Drive AMAI from directives.** AMAI already exposes a command interface
  (`tools/amai/Commands.txt`) that maps onto our controlled vocab almost 1:1 —
  `ATTACK <player>`, `BUILD G2G/TOWERS/FARMS`, `NO ATTACKS` (= defend), `CHANGE STRATEGY`,
  `STOP`. So M6 likely drives AMAI through those handlers rather than a big custom fork.
  **Open M6 question:** AMAI's *Commander* needs Jass maps, but our bridge is Lua — I'll
  determine whether to call AMAI's command functions from Lua, set AMAI globals, or use
  the dummy-target lure (design §8). This doesn't affect your steps.
- You then run the daemon against the bridge dir:
  `python -m tavern --bridge "%USERPROFILE%\Documents\Warcraft III\CustomMapData\Tavern"`
  and launch the map with `npm run test`.

## One risk I'm tracking (mine to solve, not yours)

Reforged can **write** files freely, but **repeated mid-game reads** (the Daemon→Game
direction) are the trickiest part of the Preload/FileIO approach — historically reads
happen at load. I'll validate continuous in-game reads in the first map build; if they're
unreliable, fallbacks are Preloader re-reads or AMAI's chat-command channel. This does
**not** affect your setup steps.

## Reference links
- AMAI (Reforged): <https://github.com/SMUnlimited/AMAI>
- wc3-ts-template + getting started: <https://github.com/cipherxof/wc3-ts-template> · <https://cipherxof.github.io/w3ts/docs/getting-started>
- Reforged FileIO background: [Stable Lua FileIO](https://www.hiveworkshop.com/threads/stable-lua-fileio.360424/) · [FileIO (Lua-optimized)](https://www.hiveworkshop.com/threads/fileio-lua-optimized.347049/)
