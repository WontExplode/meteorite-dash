"""Ghost (Issue #34): Replay als zweite Simulation im Gleichschritt."""

from dataclasses import replace
from pathlib import Path

from meteorite_dash.config import GHOST_ALPHA, SIM_VERSION
from meteorite_dash.context import GameContext
from meteorite_dash.ghost import Ghost
from meteorite_dash.headless import scripted_inputs
from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Recorder, Replay, ReplayStore
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.simulation import RunConfig, Simulation

CONFIG = RunConfig(seed=9001, ship="Allrounder")


def _record(config: RunConfig = CONFIG, input_seed: int = 3, ticks: int = 900) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config)
    for frame in scripted_inputs(input_seed, ticks):
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def test_ghost_replays_in_lockstep_and_confirms_consistency() -> None:
    replay = _record()
    ghost = Ghost(replay)
    assert ghost.consistent is None
    for _ in range(replay.ticks):
        assert not ghost.finished
        ghost.step()
    assert ghost.sim.tick == replay.ticks
    ghost.step()  # Eingaben aufgebraucht -> Abschluss
    assert ghost.finished
    assert ghost.consistent is True
    tick = ghost.sim.tick
    ghost.step()  # danach No-op
    assert ghost.sim.tick == tick


def test_ghost_detects_inconsistent_replay() -> None:
    replay = _record()
    tampered = replace(replay, final=replay.final._replace(coins=replay.final.coins + 1))
    ghost = Ghost(tampered)
    while not ghost.finished:
        ghost.step()
    assert ghost.consistent is False


def test_ghost_delta_is_player_minus_ghost() -> None:
    ghost = Ghost(_record())
    for _ in range(60):
        ghost.step()
    assert ghost.light_years > 0
    assert ghost.delta(ghost.light_years + 5.0) == 5.0
    assert ghost.delta(0.0) == -ghost.light_years


def test_scene_picks_best_replay_for_seed(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    store.save("short", _record(ticks=120))
    store.save("long", _record(ticks=1200))
    store.save("other", _record(replace(CONFIG, seed=1), ticks=2400))
    store.save("old", replace(_record(ticks=3000), sim_version=SIM_VERSION + 1))

    scene = GameScene(context, seed=CONFIG.seed)
    assert scene.ghost is not None
    assert scene.ghost.replay == store.load("long")
    assert GameScene(context, seed=777).ghost is None
    assert GameScene(context, seed=777, ghost=store.load("short")).ghost is not None


def test_scene_without_store_has_no_ghost(context: GameContext) -> None:
    assert GameScene(context, seed=CONFIG.seed).ghost is None


def test_scene_steps_ghost_alongside_player(context: GameContext) -> None:
    replay = _record(ticks=300)
    scene = GameScene(context, seed=CONFIG.seed, ghost=replay)
    assert scene.ghost is not None
    for _ in range(50):
        scene.step(InputFrame.NONE)
    assert scene.ghost.sim.tick == 50
    for _ in range(replay.ticks):
        scene.step(InputFrame.NONE)
    assert scene.ghost.finished
    assert scene.ghost.consistent is True


def test_ghost_never_touches_player_simulation(context: GameContext) -> None:
    with_ghost = GameScene(context, seed=CONFIG.seed, ghost=_record())
    without = GameScene(context, seed=CONFIG.seed)
    for frame in scripted_inputs(5, 400):
        with_ghost.step(frame)
        without.step(frame)
    assert with_ghost.sim.state_hash() == without.sim.state_hash()


def test_scene_draws_translucent_ghost(context: GameContext) -> None:
    scene = GameScene(context, seed=CONFIG.seed, ghost=_record())
    scene.step(InputFrame.NONE)
    scene.draw()
    image = scene.ghost_image((64, 64))
    assert image.get_alpha() == GHOST_ALPHA
    assert scene.ghost_image((64, 64)) is image  # gecacht
    assert scene.ghost_image((128, 128)).get_size() == (128, 128)
