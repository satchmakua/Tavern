import json

import pytest

from tavern.bridge import DirectiveWriter, StateFileWatcher
from tavern.config import Config
from tavern.hub import Hub
from tavern.persona import Persona
from tavern.schema import Directive
from tavern.strategy import GamePlan


def _persona(name, pid, team="ally"):
    return Persona(name=name, player_id=pid, team=team, system_prompt="x")


def test_directive_writer_serializes_chat_directives_and_plan(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    dakkar = _persona("Dakkar", 3)
    hub.register([dakkar])
    hub.set_plan("ally", GamePlan(intent="attack_Vex", posture=0.8))

    writer = DirectiveWriter(tmp_path, hub, cfg)
    # wire it the way main.py does
    hub.on_line = lambda line, source: writer.note_chat(line, source)
    hub.on_directive = writer.note_directive

    hub.post_chat("Dakkar", "going aggressive", kind="ai", source=dakkar)
    hub.record_directive(dakkar, Directive(strategy="attack_Vex", aggression=0.8, target_player="Vex"))
    assert writer.flush() is True

    data = json.loads((tmp_path / cfg.directive_file_name).read_text(encoding="utf-8"))
    assert data["chat"] == [{"id": 1, "persona": "Dakkar", "text": "going aggressive"}]
    assert data["directives"]["3"]["strategy"] == "attack_Vex"
    assert data["plan"]["ally"]["intent"] == "attack_Vex"


def test_directive_writer_human_lines_are_not_exported(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    hub.register([_persona("Dakkar", 3)])
    writer = DirectiveWriter(tmp_path, hub, cfg)
    hub.on_line = lambda line, source: writer.note_chat(line, source)

    hub.post_chat("you", "dakkar push", kind="human")  # human line, no source
    writer.flush()
    data = json.loads((tmp_path / cfg.directive_file_name).read_text(encoding="utf-8"))
    assert data["chat"] == []  # only AI lines go to the map


def test_directives_are_latest_wins_per_player(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    p = _persona("Dakkar", 3)
    hub.register([p])
    writer = DirectiveWriter(tmp_path, hub, cfg)
    hub.on_directive = writer.note_directive

    hub.record_directive(p, Directive(strategy="expand_now", aggression=0.3))
    hub.record_directive(p, Directive(strategy="attack", aggression=0.9))
    writer.flush()
    data = json.loads((tmp_path / cfg.directive_file_name).read_text(encoding="utf-8"))
    assert data["directives"]["3"] == {"strategy": "attack", "aggression": 0.9, "target_player": None}


def test_state_watcher_applies_snapshot_and_drains_chat(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    dakkar = _persona("Dakkar", 3)
    hub.register([dakkar])

    state = {
        "game_time": "01:00",
        "players": {"3": {"name": "Dakkar", "race": "Orc", "team": "ally", "food": "6/10"}},
        "new_chat": [{"speaker": "you", "text": "dakkar push their natural"}],
    }
    (tmp_path / cfg.state_file_name).write_text(json.dumps(state), encoding="utf-8")

    watcher = StateFileWatcher(tmp_path, hub, cfg)
    assert watcher.poll_once() is True

    # snapshot applied (without new_chat), human chat routed + mentioned persona woken
    assert hub.latest_state.get("game_time") == "01:00"
    assert "new_chat" not in hub.latest_state
    assert any(l.kind == "human" and "push" in l.text for l in hub.chat)
    assert dakkar.wake.is_set()


def test_state_watcher_skips_unchanged_and_bad_files(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    hub.register([_persona("Dakkar", 3)])
    watcher = StateFileWatcher(tmp_path, hub, cfg)

    assert watcher.poll_once() is False  # no file yet
    (tmp_path / cfg.state_file_name).write_text("{ not valid json", encoding="utf-8")
    assert watcher.poll_once() is False  # half-written / malformed -> skipped
