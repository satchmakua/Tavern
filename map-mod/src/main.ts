/**
 * Tavern Bridge — map entry point.
 *
 * Wires the two file channels (design §5) with the §6 synced-apply discipline:
 *   - Host exports game state to CustomMapData\TavernState.txt every ~2s.
 *   - Host polls CustomMapData\TavernDirective.txt every ~0.5s, and broadcasts
 *     its contents with BlzSendSyncData. EVERY client applies the identical
 *     payload (render chat, later drive AMAI) on the same simulation frame.
 *
 * File I/O and sync-sends are local-only side effects (no simulation state is
 * branched on them), so gating them to the host does not risk desync.
 */
import { W3TS_HOOK, addScriptHook } from "w3ts/hooks";
import { File } from "w3ts/system/file";

import { renderSystem } from "./bridge/chat";
import { applyDirectives, split } from "./bridge/directives";
import { exportState } from "./bridge/state";
import { initSync, sendSync } from "./bridge/sync";
import {
  DIRECTIVE_FILE,
  DIRECTIVE_INTERVAL,
  HOST_PLAYER_ID,
  STATE_INTERVAL,
} from "./bridge/settings";

let elapsed = 0;
let lastSyncedChatId = 0; // host-only: highest CHAT id already broadcast
let lastDirText = ""; // host-only: last directive block sent

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
  renderSystem("bridge online");

  // Host exports the state snapshot (local file write; no simulation effect).
  const stateTimer = CreateTimer();
  TimerStart(stateTimer, STATE_INTERVAL, true, () => {
    elapsed = elapsed + STATE_INTERVAL;
    if (isHost()) {
      exportState(elapsed);
    }
  });

  // Host polls the directive file and broadcasts new lines; all clients apply via sync.
  const dirTimer = CreateTimer();
  TimerStart(dirTimer, DIRECTIVE_INTERVAL, true, () => {
    if (isHost()) {
      const text = File.read(DIRECTIVE_FILE);
      if (text !== undefined && text !== "") {
        syncDirectives(text);
      }
    }
  });
}

addScriptHook(W3TS_HOOK.MAIN_AFTER, bridgeMain);
