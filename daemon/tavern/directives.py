"""Strategy track S2 — controlled directive vocabulary + normalization.

The LLM emits free-form intents ("defend_gold_mine", "pressure their natural",
"blademaster rush"). The Bridge (M6) needs to switch on a *small fixed* set to
nudge AMAI, so we normalize whatever the model says down to the canonical
vocabulary from design §4. Unrecognized intents return None (surfaced, not
invented) so tuning gaps are visible rather than silently mis-mapped.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

# Canonical intents the Bridge knows how to translate (design §4). `mass_<unit>`
# and `attack_<player>` are parameterized; the rest are bare.
CANONICAL_INTENTS = ("expand_now", "tech_up", "defend", "creep_more", "mass", "attack")

# Keyword groups, each mapped to a canonical intent. Matching is *positional*:
# the intent whose keyword appears earliest in the text wins, which handles
# "tech to tier 2 then push" (→ tech_up) vs "pressure their natural" (→ attack).
_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    # "expan" matches expand/expansion/expanding; avoid bare "xp" (it hides inside e-XP-ansion).
    (("expan", "natural", "expo", "take a base", "new base", "second base"), "expand_now"),
    (("tech", "tier", "upgrade", "advance to", "research"), "tech_up"),
    (("defend", "hold", "turtle", "protect", "fortify", "fall back", "retreat", "secure", "wall"), "defend"),
    (("creep", "experience", "hero xp", "level up", "leveling", "neutral camp"), "creep_more"),
    (("mass", "pump", "build more", "spam", "produce more", "more "), "mass"),
    (("attack", "push", "rush", "harass", "aggress", "all-in", "all in", "pressure", "siege", "focus", "engage"), "attack"),
)


def _earliest(haystack: str, needles: Iterable[str]) -> Optional[int]:
    idxs = [haystack.find(n) for n in needles]
    idxs = [i for i in idxs if i >= 0]
    return min(idxs) if idxs else None


def _extract_unit(text: str) -> Optional[str]:
    """Pull the unit out of 'mass grunts' / 'build more fiends' / 'pump archers'."""
    m = re.search(r"(?:mass|more|pump|spam|produce(?: more)?)\s+(?:of\s+)?([a-z][a-z]+)", text)
    return m.group(1).rstrip("s") if m else None


# Clean canonical forms the model may already emit — trust them, don't re-map.
_EXACT = {"expand_now", "tech_up", "defend", "creep_more", "mass", "attack"}
_MASS_RE = re.compile(r"^mass_[a-z][a-z]+$")
_ATTACK_RE = re.compile(r"^attack_([A-Za-z][\w]*)$")


def normalize_intent(raw: Optional[str], players: Iterable[str] = ()) -> tuple[Optional[str], Optional[str]]:
    """Map a free-form intent to (canonical_intent, target_player).

    Returns (None, target) when nothing maps — caller decides how to surface it.
    """
    if not raw:
        return (None, None)
    original = raw.strip()
    s = original.lower()

    # Fast path: the model already gave a clean controlled token (mass_grunt,
    # attack_Vex, expand_now). Keep it rather than re-deriving (which could blur
    # e.g. mass_paladin -> bare mass).
    if s in _EXACT:
        return (s, None)
    if _MASS_RE.match(s):
        return (s, None)
    m = _ATTACK_RE.match(original)
    if m and m.group(1).lower() not in {"player", "them", "enemy"}:
        return ("attack_" + m.group(1), m.group(1))

    target: Optional[str] = None
    for name in players:
        if name and re.search(rf"\b{re.escape(name.lower())}\b", s):
            target = name
            break

    best: Optional[str] = None
    best_pos = None
    for needles, canon in _KEYWORDS:
        pos = _earliest(s, needles)
        if pos is not None and (best_pos is None or pos < best_pos):
            best, best_pos = canon, pos

    if best == "mass":
        unit = _extract_unit(s)
        return (f"mass_{unit}" if unit else "mass", target)
    if best == "attack":
        return (f"attack_{target}" if target else "attack", target)
    return (best, target)


def is_canonical(intent: Optional[str]) -> bool:
    if not intent:
        return False
    head = intent.split("_", 1)[0]
    return head in {"expand", "tech", "defend", "creep", "mass", "attack"}
