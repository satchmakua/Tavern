"""Entry point: wire personas + Hub + LLM + FakeState into a running daemon.

M1 scope: chat-only, no game. The FakeState emitter feeds scripted state and
chat; persona loops decide what to say; everything renders to the console. Run
with --fake-llm to exercise the whole pipeline with no Ollama installed.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .fakestate import FakeStateEmitter
from .hub import Hub
from .llm import FakeLLM, LLM, LLMError, OllamaClient
from .directives import normalize_intent
from .knowledge import ground
from .persona import Persona, load_personas
from .schema import Directive, OutputParseError, parse_output
from .strategy import GamePlan, Strategist
from .summarizer import build_user_prompt, summarize, summarize_outcome, summarize_team

HERE = Path(__file__).resolve().parent
DEFAULT_SCENARIO = HERE.parent / "scenarios" / "skirmish.json"


# --------------------------------------------------------------------------- #
# console rendering
# --------------------------------------------------------------------------- #
class _Color:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _w(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.enabled else s

    def ally(self, s: str) -> str:   return self._w("32", s)
    def enemy(self, s: str) -> str:  return self._w("31", s)
    def human(self, s: str) -> str:  return self._w("36;1", s)
    def dim(self, s: str) -> str:    return self._w("2", s)
    def warn(self, s: str) -> str:   return self._w("33", s)


def _enable_windows_vt() -> bool:
    """Best-effort enable ANSI escapes on Windows; return True if color is usable."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return True
    except Exception:
        return False


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


class Renderer:
    def __init__(self, color: _Color) -> None:
        self.c = color

    def chat(self, persona: Persona, text: str) -> None:
        tag = self.c.ally(persona.name) if persona.is_ally else self.c.enemy(persona.name)
        print(f"{self.c.dim(_ts())} {tag}: {text}")

    def human(self, speaker: str, text: str) -> None:
        print(f"{self.c.dim(_ts())} {self.c.human(speaker)}: {text}")

    def event(self, text: str) -> None:
        print(f"{self.c.dim(_ts())} {self.c.dim('* ' + text)}")

    def directive(self, persona: Persona, d: Directive) -> None:
        bits = []
        if d.strategy:
            bits.append(f"strategy={d.strategy}")
        if d.aggression is not None:
            bits.append(f"aggression={d.aggression}")
        if d.target_player:
            bits.append(f"target={d.target_player}")
        print(self.c.dim(f"           » {persona.name} directive: {', '.join(bits)}"))

    def voice(self, persona: Persona, text: str) -> None:
        print(f"{self.c.dim(_ts())} 🔊 {persona.name} (voice): {text}")

    def plan(self, team: str, is_ally: bool, gp: GamePlan) -> None:
        tag = self.c.ally(team) if is_ally else self.c.enemy(team)
        print(f"{self.c.dim(_ts())} ◆ [{tag} plan] {gp.headline()}")
        if gp.rationale:
            print(self.c.dim(f"             ↳ {gp.rationale}"))

    def warn(self, text: str) -> None:
        print(self.c.warn(f"           ! {text}"))


# --------------------------------------------------------------------------- #
# coroutines
# --------------------------------------------------------------------------- #
async def persona_loop(persona: Persona, hub: Hub, llm: LLM, config: Config, render: Renderer) -> None:
    while True:
        await persona.wake.wait()
        priority = persona.consume_wake()
        now = time.monotonic()
        if not priority and (now - persona.last_chat_ts) < config.chat_min_interval:
            continue  # idle throttle: stay quiet, we spoke recently

        model = persona.model or config.default_model
        summary = summarize(hub.latest_state, persona.player_id)
        plan = hub.plan_for(persona.team)
        plan_block = plan.as_prompt_block() if plan else None
        user = build_user_prompt(summary, hub.recent_chat(), team_plan=plan_block)
        try:
            raw = await llm.complete(model=model, system=persona.system_prompt, user=user)
            out = parse_output(raw)
        except (LLMError, OutputParseError) as e:
            render.warn(f"{persona.name}: {e}")
            continue

        if out.say_in_chat:
            persona.last_chat_ts = time.monotonic()
            # rendering happens via hub.on_line so order matches other lines
            hub.post_chat(persona.name, out.say_in_chat, kind="ai", source=persona)
        if out.say_aloud:
            await hub.voice_out.put((persona, out.say_aloud))
        if out.directive:
            # S2: normalize the persona's free-form intent to the controlled vocabulary.
            players = [p.get("name") for p in hub.latest_state.get("players", {}).values() if p.get("name")]
            canon, tgt = normalize_intent(out.directive.strategy, players)
            if canon:
                out.directive.strategy = canon
                # a target only makes sense for attack intents
                if tgt and canon.startswith("attack") and not out.directive.target_player:
                    out.directive.target_player = tgt
            hub.record_directive(persona, out.directive)
            render.directive(persona, out.directive)


async def strategist_loop(
    strategist: Strategist, hub: Hub, config: Config, render: Renderer, is_ally: bool
) -> None:
    """Deliberate per-team planner (Strategy track S1): slow cadence, fuller state."""
    # First plan shortly after start (once some state exists), then on cadence.
    await asyncio.sleep(2.0)
    prev_state: dict | None = None
    while True:
        state = hub.latest_state
        summary = summarize_team(state, strategist.team)
        grounding = ground(state, strategist.team)                       # S2: RTS knowledge
        outcome = summarize_outcome(prev_state, state, strategist.team)  # S2: feedback
        try:
            plan = await strategist.propose(summary, hub.recent_chat(limit=12), outcome, grounding)
        except (LLMError, OutputParseError) as e:
            render.warn(f"strategist[{strategist.team}]: {e}")
        else:
            hub.set_plan(strategist.team, plan)
            render.plan(strategist.team, is_ally, plan)
            prev_state = state  # snapshot to diff against next round
        wait = config.strategist_interval + random.uniform(
            -config.strategist_jitter, config.strategist_jitter
        )
        await asyncio.sleep(max(5.0, wait))


async def idle_timer(persona: Persona, config: Config) -> None:
    base = persona.idle_banter_seconds or config.idle_banter_seconds
    while True:
        wait = base + random.uniform(-config.idle_banter_jitter, config.idle_banter_jitter)
        await asyncio.sleep(max(2.0, wait))
        persona.trigger(priority=False)


async def voice_consumer(hub: Hub, render: Renderer) -> None:
    """One persona speaks aloud at a time (design §3)."""
    while True:
        persona, text = await hub.voice_out.get()
        render.voice(persona, text)
        await asyncio.sleep(min(4.0, 1.0 + len(text) * 0.04))  # simulate speaking time
        hub.voice_out.task_done()


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
async def run(config: Config, args: argparse.Namespace) -> int:
    color = _Color(enabled=(not args.no_color) and _enable_windows_vt())
    render = Renderer(color)

    personas = load_personas(config.personas_dir)
    if args.persona:
        wanted = {n.lower() for n in args.persona}
        personas = [p for p in personas if p.name.lower() in wanted]
    if not personas:
        print(color.warn(f"No personas found in {config.personas_dir}"), file=sys.stderr)
        return 1

    hub = Hub(config, rng=random.Random(args.seed))
    hub.register(personas)

    def on_line(line, source: Persona | None) -> None:
        if source is not None:
            render.chat(source, line.text)
        elif line.kind == "human":
            render.human(line.speaker, line.text)
        else:
            render.event(line.text)

    hub.on_line = on_line

    llm: LLM = FakeLLM(seed=args.seed) if args.fake_llm else OllamaClient(
        config.ollama_host, config.request_timeout, config.temperature, config.keep_alive
    )

    print(color.dim(
        f"Tavern daemon — {len(personas)} persona(s): "
        + ", ".join(p.name for p in personas)
        + (f"  [fake-llm]" if args.fake_llm else f"  [ollama {config.ollama_host}]")
    ))

    # One Strategist per distinct team (Strategy track S1).
    strat_model = config.strategist_model or config.default_model
    teams = sorted({p.team for p in personas})
    strategists = {team: Strategist(team, llm, strat_model) for team in teams}
    ally_teams = {p.team for p in personas if p.is_ally}

    # Warm each distinct model into VRAM before anyone is asked to think,
    # so the first real turn isn't a multi-second cold load (design §7 latency).
    if not args.fake_llm:
        models = {p.model or config.default_model for p in personas} | {strat_model}
        for model in sorted(models):
            print(color.dim(f"  warming {model} …"))
            try:
                await llm.warmup(model=model)
            except LLMError as e:
                render.warn(f"warmup {model}: {e}")

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(voice_consumer(hub, render)))
    for team, strategist in strategists.items():
        tasks.append(asyncio.create_task(
            strategist_loop(strategist, hub, config, render, is_ally=(team in ally_teams))
        ))
    for p in personas:
        tasks.append(asyncio.create_task(persona_loop(p, hub, llm, config, render)))
        tasks.append(asyncio.create_task(idle_timer(p, config)))

    emitter: FakeStateEmitter | None = None
    duration = float(args.duration) if args.duration else 60.0
    if args.scenario:
        scenario_path = Path(args.scenario)
        if not scenario_path.exists():
            print(color.warn(f"Scenario not found: {scenario_path}"), file=sys.stderr)
            return 1
        emitter = FakeStateEmitter(hub, scenario_path, speed=args.speed)
        if not args.duration:
            duration = emitter.duration + 8.0  # tail so late reactions render
        tasks.append(asyncio.create_task(emitter.run()))

    try:
        await asyncio.sleep(duration)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await llm.aclose()

    print(color.dim(f"\n--- session over: {len(hub.directives)} directive(s) issued ---"))
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tavern", description="Tavern Companion Daemon (M1: chat-only)")
    parser.add_argument("--fake-llm", action="store_true", help="run offline with a canned LLM (no Ollama)")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO), help="FakeState scenario JSON (or 'none')")
    parser.add_argument("--persona", action="append", help="limit to persona by name (repeatable)")
    parser.add_argument("--duration", type=float, default=None, help="run for N seconds (default: scenario length + tail)")
    parser.add_argument("--speed", type=float, default=1.0, help="scenario playback speed multiplier")
    parser.add_argument("--model", default=None, help="override default Ollama model")
    parser.add_argument("--host", default=None, help="override Ollama host URL")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (deterministic banter/arbiter)")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = parser.parse_args(argv)

    try:  # so em dashes / emoji don't choke a cp1252 console
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.scenario and args.scenario.lower() == "none":
        args.scenario = None

    config = Config()
    if args.model:
        config.default_model = args.model
    if args.host:
        config.ollama_host = args.host

    try:
        return asyncio.run(run(config, args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(cli())
