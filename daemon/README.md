# /daemon — Companion Daemon + Voice Frontend (Python)

Host-side, outside the WC3 sandbox. See [design §9](../tavern-design.md) and [§3](../tavern-design.md).

**Companion Daemon** — a single asyncio process: one coroutine per persona (each with its own state, history, rate limit), a file-watcher on the map's state file, a queue subscriber for transcribed voice, a directive-file writer, a bounded shared chat history, and a state summarizer (raw snapshot → ~15–20 lines per player perspective).

**Voice Frontend** — `whisper.cpp` (`base.en`) + `silero-vad` for speech-in, Piper for speech-out. Push-to-talk via `pynput`, per-device speaker tagging, one-voice-at-a-time. Never touches the game sandbox.

Talks to the LLM via Ollama's OpenAI-compatible API at `http://localhost:11434/v1`.

_Empty — populated starting at M1._
