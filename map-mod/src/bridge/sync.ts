/**
 * Determinism / sync (design §6). Only the host reads the directive file and
 * broadcasts it with BlzSendSyncData. EVERY client (host included) catches the
 * SyncData event and applies the identical mutation on the same frame. Never
 * branch synchronous game state on a local file read.
 */
import { SYNC_PREFIX } from "./settings";

type SyncHandler = (data: string) => void;

let handler: SyncHandler | undefined;

/** Register the SyncData trigger. `onData` runs identically on all clients. */
export function initSync(onData: SyncHandler): void {
  handler = onData;
  const t = CreateTrigger();
  for (let i = 0; i < bj_MAX_PLAYER_SLOTS; i++) {
    BlzTriggerRegisterPlayerSyncEvent(t, Player(i)!, SYNC_PREFIX, false);
  }
  TriggerAddAction(t, () => {
    if (handler) {
      handler(BlzGetTriggerSyncData() ?? "");
    }
  });
}

/** Host-only: broadcast a payload to all clients (chunked to stay under limits). */
export function sendSync(data: string): void {
  BlzSendSyncData(SYNC_PREFIX, data);
}
