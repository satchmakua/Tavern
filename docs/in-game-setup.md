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

## Already done / detected ✅
- **Reforged** installed (you).
- **Node v24**, **npm 11**, **git 2.54** — present, so the TypeScript→Lua toolchain is ready.
- Daemon side of the bridge is built and tested (writes `directive.json`, reads `state.json`).

---

## Stage 1 — Locate Reforged + create the data folder  *(~10 min, you)*

1. Open **Battle.net**, launch **Warcraft III**, get to the main menu, then **quit**.
   (This first launch creates `…\Documents\Warcraft III\`, which we need.)
2. Find the install folder: in Battle.net, select **Warcraft III** → click the **gear ⚙️**
   next to the Play button → **Show in Explorer**.
3. In that folder, locate these two executables (usually under `…\_retail_\x86_64\`):
   - **`Warcraft III.exe`**
   - **`World Editor.exe`**
4. Confirm this folder exists (create it if it doesn't): 
   `%USERPROFILE%\Documents\Warcraft III\CustomMapData\` — this is our **bridge directory**.
5. **➡️ Report back to me:** the full paths to `Warcraft III.exe` and `World Editor.exe`.
   I need `Warcraft III.exe` for the template's `config.json` (`gameExecutable`), and the
   World Editor to author the map.

*(I tried to auto-detect your install and couldn't find it at the usual locations or in
the Battle.net config — so Step 2 is the reliable way to get the real path.)*

---

## Stage 2 — Enable Local Files  *(~3 min, you — or let me)*

Reforged blocks locally-saved custom maps (and local file reads) by default. You must
enable them, or Stage 3 and the bridge won't load.

- **Known method (registry):** under `HKEY_CURRENT_USER\Software\Blizzard Entertainment\Warcraft III`,
  add a **DWORD** named **`Allow Local Files`** set to **`1`**.
- I can set this for you with one command — just say "set local files" and I'll apply it
  and read it back to confirm.

You'll verify it actually took effect in Stage 3 (if a locally-saved map refuses to load,
that's this setting — ping me).

---

## Stage 3 — Prove AMAI works on Reforged  *(~20 min, you)*

This de-risks the single biggest integration point (design §11: "AMAI doesn't shift
behavior" is the top risk) **before** we build anything on top of it.

1. **Download AMAI** for Reforged: get release **2.0.4 or newer** from
   <https://github.com/SMUnlimited/AMAI/releases>. Unzip to e.g. `C:\tools\AMAI\`.
2. **Make a base map you own:** open **World Editor** → *File → Open* → built-in
   **`(4)Lost Temple`** → *File → **Save Map As*** → save to e.g.
   `C:\Tavern\maps\LostTemple.w3x`.
3. **Install AMAI into that map** (either way):
   - GUI: run **`amai-installer.exe`**, select `LostTemple.w3x`, choose the **Reforged**
     option, click **Install**; **or**
   - CMD (from the AMAI folder): `.\InstallREFORGEDToMap.bat "C:\Tavern\maps\LostTemple.w3x" 1`
4. **Test it:** Warcraft III → **Single Player → Custom Game** → load `LostTemple.w3x` →
   add a **Computer** opponent → **Start**. Watch ~5 min: a real AMAI opponent builds an
   economy, expands, and sends attack waves (clearly smarter than Blizzard's default AI).
5. **➡️ Report back to me:** "AMAI works" + the path to the AMAI-installed
   `LostTemple.w3x`. That map becomes the base I add the bridge to.

---

## After your three stages — what I do (no action from you)

- Scaffold `map-mod/` from **wc3-ts-template** (`npm install`; set `config.json` →
  `gameExecutable` = your `Warcraft III.exe`). Confirmed prereqs: Node + WC3 1.31+.
- Bundle **FileIO** + write the **Tavern Bridge** (TypeScript→Lua):
  - **Game → Daemon:** every ~2 s, `FileIO.Save` a `state.json`-shaped snapshot + new
    human chat into `CustomMapData\Tavern\`.
  - **Daemon → Game:** host reads `directive.json` via `FileIO.Load`, then **`BlzSendSyncData`**
    → every client renders the line with `BlzDisplayChatMessage` and applies the AMAI
    directive on the same frame (design §6 — synced from the first line).
- Integrate the **AMAI fork** (`commander_remote.lua`) so directives nudge AMAI.
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
