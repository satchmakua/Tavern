import json

from tavern.bridge import DirectiveWriter, StateFileWatcher
from tavern.config import Config
from tavern.hub import Hub
from tavern.persona import Persona
from tavern.schema import Directive
from tavern.wc3codec import decode_file, encode_file


def _persona(name, pid, team="ally"):
    return Persona(name=name, player_id=pid, team=team, system_prompt="x")


def test_directive_writer_emits_delimited_lines(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    dakkar = _persona("Dakkar", 3)
    hub.register([dakkar])
    writer = DirectiveWriter(tmp_path, hub, cfg)
    hub.on_line = lambda line, source: writer.note_chat(line, source)
    hub.on_directive = writer.note_directive

    hub.post_chat("Dakkar", "going aggressive", kind="ai", source=dakkar)
    hub.record_directive(dakkar, Directive(strategy="attack_Vex", aggression=0.8, target_player="Vex"))
    assert writer.flush() is True

    text = (tmp_path / cfg.directive_file_name).read_text(encoding="utf-8")
    assert "CHAT|1|Dakkar|going aggressive" in text
    assert "DIR|3|attack_Vex|0.8|Vex" in text


def test_human_lines_are_not_exported(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    hub.register([_persona("Dakkar", 3)])
    writer = DirectiveWriter(tmp_path, hub, cfg)
    hub.on_line = lambda line, source: writer.note_chat(line, source)

    hub.post_chat("you", "dakkar push", kind="human")  # no source -> not exported
    writer.flush()
    assert "CHAT" not in (tmp_path / cfg.directive_file_name).read_text(encoding="utf-8")


def test_directives_latest_wins_per_player(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    p = _persona("Dakkar", 3)
    hub.register([p])
    writer = DirectiveWriter(tmp_path, hub, cfg)
    hub.on_directive = writer.note_directive

    hub.record_directive(p, Directive(strategy="expand_now", aggression=0.3))
    hub.record_directive(p, Directive(strategy="attack", aggression=0.9))
    writer.flush()
    lines = [l for l in (tmp_path / cfg.directive_file_name).read_text(encoding="utf-8").split("\n")
             if l.startswith("DIR|3")]
    assert lines == ["DIR|3|attack|0.9|"]


def test_wc3_mode_writes_seq_files_and_cursor(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    p = _persona("Dakkar", 3)
    hub.register([p])
    writer = DirectiveWriter(tmp_path, hub, cfg, wc3=True)
    hub.on_directive = writer.note_directive
    hub.on_line = lambda line, source: writer.note_chat(line, source)

    hub.record_directive(p, Directive(strategy="attack_Vex", aggression=0.8, target_player="Vex"))
    writer.flush()  # -> TavernDir0.txt + cursor
    seq0 = (tmp_path / "TavernDir0.txt").read_text(encoding="utf-8")
    assert "PreloadFiles" in seq0  # w3ts File wrapping for the map's Preloader
    assert decode_file(seq0) == "DIR|3|attack_Vex|0.8|Vex"
    # cursor = "<seq>|<maxChatId>" so the map skips the backlog at start
    assert decode_file((tmp_path / cfg.directive_cursor_name).read_text(encoding="utf-8")) == "0|0"

    # a new change increments the seq filename + cursor (fresh name defeats the cache)
    hub.post_chat("Dakkar", "hi", kind="ai", source=p)
    writer.flush()  # -> TavernDir1.txt
    assert (tmp_path / "TavernDir1.txt").exists()
    assert decode_file((tmp_path / cfg.directive_cursor_name).read_text(encoding="utf-8")) == "1|1"


def test_wc3_seq_files_rotate_and_prune(tmp_path):
    cfg = Config()
    cfg.directive_seq_keep = 3
    hub = Hub(cfg)
    p = _persona("Dakkar", 3)
    hub.register([p])
    writer = DirectiveWriter(tmp_path, hub, cfg, wc3=True)
    hub.on_directive = writer.note_directive
    for _ in range(6):
        hub.record_directive(p, Directive(strategy="attack", aggression=0.5))
        writer._dirty = True
        writer.flush()
    # only the last `keep` seq files remain
    remaining = sorted(f.name for f in tmp_path.glob("TavernDir[0-9]*.txt"))
    assert remaining == ["TavernDir3.txt", "TavernDir4.txt", "TavernDir5.txt"]


def test_state_watcher_raw(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    dakkar = _persona("Dakkar", 3)
    hub.register([dakkar])
    state = {
        "game_time": "01:00",
        "players": {"3": {"name": "Dakkar", "team": "ally"}},
        "new_chat": [{"speaker": "you", "text": "dakkar push their natural"}],
    }
    (tmp_path / cfg.state_file_name).write_text(json.dumps(state), encoding="utf-8")
    watcher = StateFileWatcher(tmp_path, hub, cfg)
    assert watcher.poll_once() is True
    assert hub.latest_state.get("game_time") == "01:00"
    assert "new_chat" not in hub.latest_state
    assert dakkar.wake.is_set()  # mentioned human chat woke the persona


def test_state_watcher_wc3_decodes(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    hub.register([_persona("Dakkar", 3)])
    state = {"game_time": "02:00", "players": {"3": {"name": "Dakkar", "team": "ally"}}}
    (tmp_path / cfg.state_file_name).write_text(encode_file(json.dumps(state)), encoding="utf-8")
    watcher = StateFileWatcher(tmp_path, hub, cfg, wc3=True)
    assert watcher.poll_once() is True
    assert hub.latest_state.get("game_time") == "02:00"


def test_state_watcher_skips_unchanged_and_bad(tmp_path):
    cfg = Config()
    hub = Hub(cfg)
    hub.register([_persona("Dakkar", 3)])
    watcher = StateFileWatcher(tmp_path, hub, cfg)
    assert watcher.poll_once() is False  # no file yet
    (tmp_path / cfg.state_file_name).write_text("{ not valid json", encoding="utf-8")
    assert watcher.poll_once() is False  # malformed -> skipped
