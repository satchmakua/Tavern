/**
 * Tavern Bridge — map entry point.
 *
 * Two file channels (design §5) with the §6 synced-apply discipline:
 *   - Host exports game state to CustomMapData\TavernState.txt every ~2s.
 *   - Host reads directives from CustomMapData\TavernDir<n>.txt. Because Reforged's
 *     Preloader caches a filename for the whole session (the 1.33+ cache bug), each
 *     update arrives on a NEW incrementing filename. The host reads a cursor file
 *     ONCE at start (to skip the backlog), then reads forward through the seq files,
 *     broadcasting new lines with BlzSendSyncData so EVERY client renders identically.
 *
 * File I/O and sync-sends are local-only side effects (no simulation state is
 * branched on them), so gating them to the host does not risk desync.
 */
import { W3TS_HOOK, addScriptHook } from "w3ts/hooks";
import { File } from "w3ts/system/file";

import { renderSystem } from "./bridge/chat";
import { initChatCapture } from "./bridge/chatcapture";
import { applyDirectives, split } from "./bridge/directives";
import { exportState } from "./bridge/state";
import { initSync, sendSync } from "./bridge/sync";
import {
  DIRECTIVE_CURSOR_FILE,
  DIRECTIVE_INTERVAL,
  DIRECTIVE_SEQ_PREFIX,
  HOST_PLAYER_ID,
  STATE_INTERVAL,
} from "./bridge/settings";

let elapsed = 0;
let lastSyncedChatId = 0; // host-only: highest CHAT id already broadcast
let lastDirText = ""; // host-only: last directive block sent
let readSeq = 0; // host-only: highest directive seq file consumed
let cursorInit = false; // host-only: have we read the start cursor yet
let debugTicks = 0;

function isHost(): boolean {
  return GetPlayerId(GetLocalPlayer()) === HOST_PLAYER_ID;
}

/**
 * Broadcast only *new* content, one line per BlzSendSyncData (each well under the
 * ~255-char sync limit). New CHAT lines go once (deduped by id); DIR lines re-send
 * only when the directive block changes.
 */
function syncDirectives(text: string): void {
  const dirLines: string[] = [];
  for (const line of split(text, "\n")) {
    if (line === "") continue;
    if (string.sub(line, 1, 5) === "CHAT|") {
      const id = tonumber(split(line, "|")[1]) ?? 0;
      if (id > lastSyncedChatId) {
        lastSyncedChatId = id;
        sendSync(line);
      }
    } else if (string.sub(line, 1, 4) === "DIR|") {
      dirLines.push(line);
    }
  }
  const dirText = dirLines.join("\n");
  if (dirText !== lastDirText) {
    lastDirText = dirText;
    for (const d of dirLines) sendSync(d);
  }
}

function bridgeMain(): void {
  // Every client applies synced directives identically (§6).
  initSync(applyDirectives);
  initChatCapture(); // host captures human chat → daemon (game → daemon)
  renderSystem("bridge online — type to talk to the AI");

  // Host exports the state snapshot (local file write; no simulation effect).
  const stateTimer = CreateTimer();
  TimerStart(stateTimer, STATE_INTERVAL, true, () => {
    elapsed = elapsed + STATE_INTERVAL;
    if (isHost()) {
      exportState(elapsed);
    }
  });

  // Host reads forward through the directive seq files and broadcasts new lines.
  const dirTimer = CreateTimer();
  TimerStart(dirTimer, DIRECTIVE_INTERVAL, true, () => {
    if (!isHost()) return;

    // One-time: read the cursor to skip the pre-game backlog (seq) + old chat (maxId).
    if (!cursorInit) {
      const cur = File.read(DIRECTIVE_CURSOR_FILE);
      if (cur === undefined) return; // daemon not writing yet
      const parts = split(cur, "|");
      readSeq = tonumber(parts[0]) ?? 0;
      lastSyncedChatId = tonumber(parts[1]) ?? 0;
      cursorInit = true;
      renderSystem(`linked to daemon (seq ${readSeq})`);
    }

    // Each seq file is a fresh filename → not hit by the Preload cache.
    for (;;) {
      const c = File.read(`${DIRECTIVE_SEQ_PREFIX}${readSeq + 1}.txt`);
      if (c === undefined) break;
      readSeq++;
      syncDirectives(c);
    }

    debugTicks++;
    if (debugTicks % 20 === 0) renderSystem(`seq ${readSeq}`); // heartbeat every ~10s
  });
}

addScriptHook(W3TS_HOOK.MAIN_AFTER, bridgeMain);
