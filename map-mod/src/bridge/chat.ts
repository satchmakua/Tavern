/**
 * Rendering persona speech + system messages in-game. Called from inside the
 * SyncData handler so every client renders identically (design §5.2 / §6).
 */
import { PERSONA_COLOR } from "./settings";

/** Render a persona chat line, attributed by name. */
export function renderChat(persona: string, text: string): void {
  BlzDisplayChatMessage(GetLocalPlayer(), 0, `${PERSONA_COLOR}${persona}|r: ${text}`);
}

/** Dim system/debug line (bridge status, directive tracing). */
export function renderSystem(text: string): void {
  DisplayTimedTextToPlayer(GetLocalPlayer(), 0, 0, 8, `|cff888888[Tavern]|r ${text}`);
}
