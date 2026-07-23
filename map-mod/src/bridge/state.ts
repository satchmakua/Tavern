/**
 * Game → Daemon: export a compact state snapshot to CustomMapData\TavernState.txt.
 * Shape matches what the daemon summarizers consume (players{name,race,team,
 * gold,lumber,food,...}). Writing a file is local-only and does not affect the
 * simulation, so it's safe to do on the host without syncing.
 */
import { File } from "w3ts/system/file";
import { drainChat } from "./chatcapture";
import { STATE_FILE } from "./settings";

function jsonEscape(s: string): string {
  s = string.gsub(s, "\\", "\\\\")[0];
  s = string.gsub(s, '"', '\\"')[0];
  return s;
}

function raceName(p: player): string {
  const r = GetPlayerRace(p);
  if (r === RACE_HUMAN) return "Human";
  if (r === RACE_ORC) return "Orc";
  if (r === RACE_UNDEAD) return "Undead";
  if (r === RACE_NIGHTELF) return "Night Elf";
  return "Unknown";
}

/** Is this an active user/computer player we should report? */
function isActive(p: player): boolean {
  const ctrl = GetPlayerController(p);
  return (
    GetPlayerSlotState(p) === PLAYER_SLOT_STATE_PLAYING &&
    (ctrl === MAP_CONTROL_USER || ctrl === MAP_CONTROL_COMPUTER)
  );
}

function playerJson(p: player, localHuman: player): string {
  const slot = GetPlayerId(p) + 1; // 1-based, matches persona player_id
  const gold = GetPlayerState(p, PLAYER_STATE_RESOURCE_GOLD);
  const lumber = GetPlayerState(p, PLAYER_STATE_RESOURCE_LUMBER);
  const foodUsed = GetPlayerState(p, PLAYER_STATE_RESOURCE_FOOD_USED);
  const foodCap = GetPlayerState(p, PLAYER_STATE_RESOURCE_FOOD_CAP);
  const team = IsPlayerAlly(p, localHuman) ? "ally" : "enemy";
  const name = jsonEscape(GetPlayerName(p) ?? `Player ${slot}`);
  return (
    `"${slot}":{"name":"${name}","race":"${raceName(p)}","team":"${team}",` +
    `"gold":${gold},"lumber":${lumber},"food":"${foodUsed}/${foodCap}"}`
  );
}

/** Serialize the current board and write it for the daemon to read. */
export function exportState(gameSeconds: number): void {
  const localHuman = Player(0)!;
  const parts: string[] = [];
  for (let i = 0; i < bj_MAX_PLAYERS; i++) {
    const p = Player(i)!;
    if (isActive(p)) {
      parts.push(playerJson(p, localHuman));
    }
  }
  const mins = math.floor(gameSeconds / 60);
  const secs = math.floor(gameSeconds % 60);
  const clock = `${mins < 10 ? "0" : ""}${mins}:${secs < 10 ? "0" : ""}${secs}`;

  // Drain any human chat typed since the last export → new_chat (daemon routes it).
  let newChat = "";
  const chat = drainChat();
  if (chat.length > 0) {
    const items = chat.map(
      (c) => `{"speaker":"${jsonEscape(c.speaker)}","text":"${jsonEscape(c.text)}"}`
    );
    newChat = `,"new_chat":[${table.concat(items, ",")}]`;
  }

  const json = `{"game_time":"${clock}","players":{${table.concat(parts, ",")}}${newChat}}`;
  File.write(STATE_FILE, json);
}
