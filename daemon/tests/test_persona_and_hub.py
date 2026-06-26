import asyncio

import pytest

from tavern.config import Config
from tavern.hub import Hub
from tavern.persona import Persona, load_personas


def _persona(name, pid, team="ally"):
    return Persona(name=name, player_id=pid, team=team, system_prompt="x")


def test_repo_personas_load_with_unique_ids():
    personas = load_personas(Config().personas_dir)
    assert len(personas) >= 4
    ids = [p.player_id for p in personas]
    assert len(ids) == len(set(ids))  # unique
    assert {"Dakkar", "Sera", "Vex", "Grollum"} <= {p.name for p in personas}


def test_mention_detection_word_boundary():
    p = _persona("Vex", 5)
    assert p.mentioned_in("vex you're done")
    assert p.mentioned_in("nice one, Vex.")
    assert not p.mentioned_in("the vexing problem")  # substring, not a mention


@pytest.mark.asyncio
async def test_human_mention_wakes_named_persona():
    cfg = Config()
    hub = Hub(cfg)
    dakkar, sera = _persona("Dakkar", 3), _persona("Sera", 4)
    hub.register([dakkar, sera])

    hub.post_chat("you", "dakkar push with me", kind="human")
    assert dakkar.wake.is_set()
    assert not sera.wake.is_set()


@pytest.mark.asyncio
async def test_ai_to_ai_turn_cap():
    cfg = Config()
    cfg.ai_to_ai_turn_cap = 2
    hub = Hub(cfg)
    a, b = _persona("Dakkar", 3), _persona("Vex", 5, team="enemy")
    hub.register([a, b])

    # b keeps naming a; a should only be woken `cap` times before falling silent
    for _ in range(5):
        b.consume_wake() if b.wake.is_set() else None
        a.consume_wake()  # clear so we can see re-trigger
        hub.post_chat("Vex", "dakkar you're finished", kind="ai", source=b)
    assert a.ai_reply_counts["Vex"] == 2  # capped


@pytest.mark.asyncio
async def test_broadcast_event_wakes_only_one():
    import random

    cfg = Config()
    hub = Hub(cfg, rng=random.Random(0))
    ps = [_persona(n, i) for i, n in enumerate(["A", "B", "C", "D"], start=1)]
    hub.register(ps)

    hub.emit_event("a hero died", broadcast=True)
    awoken = [p for p in ps if p.wake.is_set()]
    assert len(awoken) == 1  # arbiter picked exactly one
