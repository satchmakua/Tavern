/**
 * Tavern Bridge — shared settings (map side).
 *
 * Files live in Documents\Warcraft III\CustomMapData\ (w3ts `File` constraint),
 * must end in .txt/.pld, and are read/written via the Preload exploit. The daemon
 * points `--bridge` at that CustomMapData folder. See docs/bridge-protocol.md.
 */

// Filenames inside CustomMapData (prefix instead of a subfolder, which Preload
// can't create). The daemon writes TavernDirective.txt, reads TavernState.txt.
export const STATE_FILE = "TavernState.txt";
export const DIRECTIVE_FILE = "TavernDirective.txt";

// Cadences (seconds).
export const STATE_INTERVAL = 2.0; // how often the host exports game state
export const DIRECTIVE_INTERVAL = 0.5; // how often the host polls for directives

// BlzSendSyncData prefix for the §6 synced apply path.
export const SYNC_PREFIX = "TVN";

// Which player is the "host" that owns file I/O (single-machine test = slot 0).
// Only this client reads directives + sends the sync; every client applies it.
export const HOST_PLAYER_ID = 0;

// Chat color for rendered persona lines (purple).
export const PERSONA_COLOR = "|cff9b59b6";
