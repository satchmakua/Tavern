# /scripts — Launchers and dev tooling

Operational scripts for running and developing Tavern.

## Available

- **`setup.ps1`** — M0 environment setup. Confirms Ollama is installed, ensures the server is up at `:11434` (starts it if needed), pulls the daemon's LLM models, and verifies them. Idempotent.
  ```powershell
  ./scripts/setup.ps1
  # override models: ./scripts/setup.ps1 -Models "llama3.1:8b","qwen2.5:7b"
  ```

## Planned (M8 packaging, design §10)

- **One-click launcher** (PowerShell is plenty) — starts Ollama, the Companion Daemon, and the Voice Frontend together.
- Dev helpers — `FakeState` replay runner, whisper.cpp/Piper install, log tailing.
