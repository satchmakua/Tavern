/**
 * Daemon → Game: parse and apply the directive payload (which arrived via sync,
 * so this runs identically on every client). Wire format is newline-separated,
 * pipe-delimited lines — trivial to parse without a Lua JSON reader:
 *
 *   CHAT|<id>|<persona>|<text>
 *   DIR|<playerId>|<strategy>|<aggression>|<target>
 *
 * CHAT lines carry a monotonic id so each renders exactly once. DIR is latest-
 * wins per player (M6 will route it into AMAI; for now it's traced on screen).
 */
import { renderChat, renderSystem } from "./chat";

let lastChatId = 0;

/** Split on a literal separator (Lua has no string.split). */
export function split(s: string, sep: string): string[] {
  const out: string[] = [];
  let start = 1;
  for (;;) {
    const [i, j] = string.find(s, sep, start, true);
    if (i === undefined) {
      out.push(string.sub(s, start));
      break;
    }
    out.push(string.sub(s, start, (i as number) - 1));
    start = (j as number) + 1;
  }
  return out;
}

export function applyDirectives(text: string): void {
  for (const line of split(text, "\n")) {
    if (line === "") continue;
    const f = split(line, "|");
    if (f[0] === "CHAT" && f.length >= 4) {
      const id = tonumber(f[1]) ?? 0;
      if (id > lastChatId) {
        lastChatId = id;
        renderChat(f[2], f[3]);
      }
    } else if (f[0] === "DIR" && f.length >= 3) {
      // TODO(M6): route into AMAI via its command interface (tools/amai/Commands.txt).
      const target = f.length >= 5 && f[4] !== "" ? ` @${f[4]}` : "";
      renderSystem(`directive p${f[1]} → ${f[2]}${target}`);
    }
  }
}
