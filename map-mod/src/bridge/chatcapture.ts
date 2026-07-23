/**
 * Game → Daemon: capture what human players type in chat, so the daemon can route
 * it to the personas (an @-mention wakes that persona to reply). Buffered lines are
 * drained into each state export (`state.ts`).
 *
 * Only the host buffers (only the host exports state), and only USER-controlled
 * players' messages are captured (so AMAI's own chat isn't fed back as human input).
 * Buffering is a local side effect, so the GetLocalPlayer branch is desync-safe.
 */
import { HOST_PLAYER_ID } from "./settings";

interface Captured {
  speaker: string;
  text: string;
}

let buffer: Captured[] = [];

export function initChatCapture(): void {
  const t = CreateTrigger();
  for (let i = 0; i < bj_MAX_PLAYERS; i++) {
    TriggerRegisterPlayerChatEvent(t, Player(i)!, "", false); // "" + false = any message
  }
  TriggerAddAction(t, () => {
    if (GetPlayerId(GetLocalPlayer()) !== HOST_PLAYER_ID) return;
    const p = GetTriggerPlayer();
    if (p === undefined || GetPlayerController(p) !== MAP_CONTROL_USER) return;
    const msg = GetEventPlayerChatString();
    if (msg !== undefined && msg !== "") {
      buffer.push({ speaker: GetPlayerName(p) ?? "player", text: msg });
    }
  });
}

/** Return and clear the buffered human chat lines. */
export function drainChat(): Captured[] {
  const out = buffer;
  buffer = [];
  return out;
}
