/**
 * Tavern Bridge — shared settings (map side).
 *
 * Files live in Documents\Warcraft III\CustomMapData\ (w3ts `File` constraint),
 * must end in .txt/.pld, and are read/written via the Preload exploit. The daemon
 * points `--bridge` at that CustomMapData folder. See docs/bridge-protocol.md.
 */

// Filenames inside CustomMapData (prefix instead of a subfolder, which Preload
// can't create). The map writes TavernState.txt and reads rotating TavernDir<n>.txt.
export const STATE_FILE = "TavernState.txt";
// Directives arrive on incrementing filenames to defeat the Reforged Preload cache
// bug (a filename, once read, is cached for the whole session). The cursor file is
// read ONCE at start to skip the pre-game backlog.
export const DIRECTIVE_SEQ_PREFIX = "TavernDir"; // TavernDir0.txt, TavernDir1.txt, …
export const DIRECTIVE_CURSOR_FILE = "TavernDirCursor.txt";

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
