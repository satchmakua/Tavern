"""Phase D — WC3 codec. The map's file I/O is w3ts `File` (Preload exploit), which
wraps content in a `PreloadFiles` JASS function on disk so `File.read` (via
`Preloader`) can recover it. For the daemon to exchange files with the map it must
speak this exact format. The byte format was captured from a real in-game
`File.write` (docs/bridge-protocol.md) and mirrored here.

  encode_file(text) -> the on-disk .txt the map's File.read can parse (daemon writes)
  decode_file(disk) -> the original text the map's File.write stored (daemon reads)

w3ts specifics (node_modules/w3ts/system/file.lua): escape char = chr(27); `"` ->
ESC+'q', ESC -> ESC+ESC; content chunked at 259 chars; dummy ability icon 1097690227
(= FourCC 'Amls').
"""
from __future__ import annotations

import re
from typing import Optional

ESC = chr(27)
PRELOAD_LIMIT = 259
DUMMY_ABILITY = 1097690227  # FourCC("Amls"), w3ts File.dummyAbility

_HEADER = (
    "function PreloadFiles takes nothing returns nothing\n\n"
    "\tcall PreloadStart()\n"
    '\tcall Preload( "")\n'
    "//! beginusercode\n"
    "local o=''\n"
    "Preload=function(s)o=o..s end\n"
    "PreloadEnd=function()end\n"
    "//!endusercode\n"
    '//" )\n'
)
_FOOTER = (
    '\tcall Preload( "")\n'
    "//! beginusercode\n"
    f"BlzSetAbilityIcon({DUMMY_ABILITY},o)\n"
    "//!endusercode\n"
    '//" )\n'
    "\tcall PreloadEnd( 0.0 )\n\n"
    "endfunction\n\n\n"
)

# Content chunks are clean single-line `call Preload( "<chunk>" )` with a space
# before ')'. The header/footer use `"")` (no space), so this matches content only.
_CHUNK_RE = re.compile(r'call Preload\( "([^"]*)" \)')


def escape(s: str) -> str:
    # ESC first, then quote — matching w3ts File.escape order.
    return s.replace(ESC, ESC + ESC).replace('"', ESC + "q")


def unescape(s: str) -> str:
    # quote first, then ESC — matching w3ts File.unescape order.
    return s.replace(ESC + "q", '"').replace(ESC + ESC, ESC)


def encode_file(content: str) -> str:
    """Produce the on-disk .txt the map's `File.read` recovers as `content`."""
    esc = escape(content)
    parts = [_HEADER]
    for i in range(0, len(esc), PRELOAD_LIMIT):
        parts.append(f'\tcall Preload( "{esc[i : i + PRELOAD_LIMIT]}" )\n')
    parts.append(_FOOTER)
    return "".join(parts)


def decode_file(disk: str) -> Optional[str]:
    """Recover the content the map's `File.write` stored. None if not a File."""
    chunks = _CHUNK_RE.findall(disk)
    if chunks:
        return unescape("".join(chunks))
    # a valid File with empty content has the wrapper but no content chunks -> ""
    if "function PreloadFiles" in disk and "BlzSetAbilityIcon" in disk:
        return ""
    return None
