"""M3 — Voice Frontend. TTS via Piper, STT via whisper.cpp, push-to-talk capture.

Entirely host-side; never touches the game sandbox (design §3).

- `PiperTTS` / `WhisperSTT` shell out to the installed binaries (see config /
  scripts/setup.ps1) and need no extra pip deps.
- `VoiceInput` (push-to-talk mic capture) lazily imports `sounddevice` + `pynput`
  so the rest of the daemon imports fine without them.

Speaker routing is by *device* (design §3): each human on a separate mic, each
`VoiceInput` tagged with a `speaker`. TTS plays one line at a time (the daemon's
single voice-consumer coroutine already serializes), into headsets — never room
speakers — to avoid the TTS→mic feedback loop.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

from .config import Config

# Placeholder voice ids used in the persona YAMLs → an actually-installed voice.
# (Only two voices ship by default; expand via scripts/setup.ps1, then map here.)
_VOICE_ALIASES = {
    "en_US-gruff": "en_US-ryan-medium",
    "en_US-cool": "en_US-lessac-medium",
    "en_US-calm": "en_US-lessac-medium",
    "en_US-dry": "en_US-ryan-medium",
    "en_GB-dry": "en_US-ryan-medium",
}


def _play_wav(path: Path) -> None:
    """Blocking playback (keeps one-voice-at-a-time). Best-effort across OSes."""
    try:
        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", str(path)], check=False)
        else:
            subprocess.run(["aplay", "-q", str(path)], check=False)
    except Exception:
        pass  # no audio device / player — synthesis still succeeded


class PiperTTS:
    def __init__(self, config: Config) -> None:
        self.exe = config.piper_exe
        self.voices_dir = config.piper_voices_dir
        self.default_voice = config.default_voice
        self._available = self._scan()
        self._warned: set[str] = set()

    def _scan(self) -> dict[str, Path]:
        if not self.voices_dir.exists():
            return {}
        return {p.stem: p for p in self.voices_dir.glob("*.onnx")}

    @property
    def available(self) -> bool:
        return self.exe.exists() and bool(self._available)

    def resolve(self, voice: Optional[str]) -> Optional[Path]:
        """persona.voice → an installed .onnx, via alias map then default fallback."""
        name = _VOICE_ALIASES.get(voice or "", voice or "")
        if name in self._available:
            return self._available[name]
        if self.default_voice in self._available:
            return self._available[self.default_voice]
        return next(iter(self._available.values()), None)

    def synth(self, text: str, voice: Optional[str]) -> Optional[Path]:
        """Synthesize `text` with `voice` → a wav path (None if Piper unavailable)."""
        model = self.resolve(voice)
        if not model or not self.exe.exists():
            return None
        out = Path(tempfile.gettempdir()) / f"tavern_tts_{abs(hash(text)) % 10**8}.wav"
        try:
            subprocess.run(
                [str(self.exe), "-m", str(model), "-f", str(out)],
                input=text.encode("utf-8"),
                cwd=str(self.exe.parent),  # so espeak-ng-data + dlls resolve
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out if out.exists() else None

    def speak(self, text: str, voice: Optional[str]) -> None:
        wav = self.synth(text, voice)
        if wav:
            _play_wav(wav)


def _clean_transcript(raw: str) -> str:
    return " ".join(line.strip() for line in raw.splitlines() if line.strip()).strip()


class WhisperSTT:
    def __init__(self, config: Config) -> None:
        self.exe = config.whisper_exe
        self.model = config.whisper_model

    @property
    def available(self) -> bool:
        return self.exe.exists() and self.model.exists()

    def transcribe(self, wav: Path) -> str:
        if not self.available:
            return ""
        try:
            proc = subprocess.run(
                [str(self.exe), "-m", str(self.model), "-f", str(wav), "-nt", "-np"],
                cwd=str(self.exe.parent),  # so whisper/ggml dlls resolve
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return _clean_transcript(proc.stdout)


def _write_wav(path: Path, frames, samplerate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(samplerate)
        w.writeframes(frames.tobytes())


class VoiceInput:
    """Push-to-talk: hold the key → record mic → whisper → on_utterance(speaker, text).

    Lazily imports sounddevice + pynput. Construct with the asyncio loop so the
    callback (fired from a worker thread) can be marshalled back safely.
    """

    def __init__(
        self,
        config: Config,
        stt: WhisperSTT,
        on_utterance: Callable[[str, str], None],
    ) -> None:
        self.config = config
        self.stt = stt
        self.on_utterance = on_utterance
        self.speaker = config.speaker_name
        self._recording = False
        self._frames: list = []
        self._stream = None
        self._listener = None
        self._sd = None

    def _match_key(self, key) -> bool:
        from pynput import keyboard

        want = self.config.ptt_key
        special = getattr(keyboard.Key, want, None)
        if special is not None:
            return key == special
        return getattr(key, "char", None) == want

    def _on_press(self, key) -> None:
        if self._recording or not self._match_key(key):
            return
        self._recording = True
        self._frames = []

        def _cb(indata, frames, time_info, status):
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = self._sd.InputStream(
            samplerate=self.config.mic_samplerate,
            channels=1,
            dtype="int16",
            device=self.config.mic_device,
            callback=_cb,
        )
        self._stream.start()

    def _on_release(self, key) -> None:
        if not self._recording or not self._match_key(key):
            return
        self._recording = False
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        threading.Thread(target=self._finish, args=(list(self._frames),), daemon=True).start()

    def _finish(self, frames: list) -> None:
        if not frames:
            return
        import numpy as np

        audio = np.concatenate(frames, axis=0)
        wav = Path(tempfile.gettempdir()) / "tavern_ptt.wav"
        _write_wav(wav, audio, self.config.mic_samplerate)
        text = self.stt.transcribe(wav)
        if text:
            self.on_utterance(self.speaker, text)

    def start(self) -> None:
        """Begin listening for the push-to-talk key. Raises if deps are missing."""
        import sounddevice as sd
        from pynput import keyboard

        self._sd = sd
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
