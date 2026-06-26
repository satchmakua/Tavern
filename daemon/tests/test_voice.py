from tavern.config import Config
from tavern.voice import PiperTTS, _clean_transcript


def _tts_with_voices(tmp_path, *stems):
    for s in stems:
        (tmp_path / f"{s}.onnx").write_text("x")  # dummy model files
    cfg = Config()
    cfg.piper_voices_dir = tmp_path
    cfg.default_voice = "en_US-lessac-medium"
    return PiperTTS(cfg)


def test_voice_alias_resolves_to_installed(tmp_path):
    tts = _tts_with_voices(tmp_path, "en_US-ryan-medium", "en_US-lessac-medium")
    # persona placeholder ids map through the alias table
    assert tts.resolve("en_US-gruff").stem == "en_US-ryan-medium"
    assert tts.resolve("en_US-calm").stem == "en_US-lessac-medium"
    # an exact installed stem resolves to itself
    assert tts.resolve("en_US-ryan-medium").stem == "en_US-ryan-medium"


def test_voice_falls_back_to_default(tmp_path):
    tts = _tts_with_voices(tmp_path, "en_US-ryan-medium", "en_US-lessac-medium")
    assert tts.resolve("totally-unknown").stem == "en_US-lessac-medium"  # default
    assert tts.resolve(None).stem == "en_US-lessac-medium"


def test_no_voices_resolves_to_none(tmp_path):
    cfg = Config()
    cfg.piper_voices_dir = tmp_path  # empty
    tts = PiperTTS(cfg)
    assert tts.available is False
    assert tts.resolve("anything") is None


def test_transcript_cleaning():
    assert _clean_transcript("\n  And so my fellow Americans  \n\n") == "And so my fellow Americans"
    assert _clean_transcript("") == ""
