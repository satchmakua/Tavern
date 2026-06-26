# /personas — AI player definitions (YAML)

One file per AI player. See [design §4](../tavern-design.md).

Each persona is a short system prompt — name, race lean, temperament, constraints — plus runtime metadata (team, model tier, Piper voice). **Keep prompts short:** they leak into every response and burn context. Target 6–12 personas mixing races and tempers; assign them to teams to fill whatever lobby you're playing (team game or FFA).

Model tiering (§7): focus personas (your teammates, the opponent you're fighting) run the 8B; noisier enemy banter runs a 4B.

Each LLM turn returns one JSON object:

```json
{
  "say_in_chat": "rax done, going treants",
  "say_aloud": null,
  "directive": {"strategy": "expand_then_tech", "aggression": 0.3, "target_player": null},
  "thinking": "teammate just lost their altar, hold the push"
}
```

`thinking` is logged for debugging and read by nothing. The daemon acts on the rest.

See [dakkar.yaml](dakkar.yaml) for a worked example.
