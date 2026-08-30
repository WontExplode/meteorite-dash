"""Share-Code: kompaktes Binär-/Textformat eines Replays, defensiv beim Entpacken."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from meteorite_dash import sharecode
from meteorite_dash.difficulty import DirectorKind
from meteorite_dash.headless import scripted_inputs
from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Recorder, Replay, RunMode
from meteorite_dash.simulation import RunConfig, Simulation

GOLDEN_DIR = Path(__file__).parent / "replays"
CONFIG = RunConfig(seed=4711, ship="Allrounder", accessories=("shield", "magnet"))


def _record(config: RunConfig, input_seed: int, ticks: int, **kwargs: object) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config, mode=RunMode.DAILY, label="2026-08-30")
    for frame in scripted_inputs(input_seed, ticks):
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def _golden(name: str) -> Replay:
    replay = Replay.from_dict(json.loads((GOLDEN_DIR / f"{name}.json").read_text()))
    assert replay is not None
    return replay


@pytest.mark.parametrize("name", ["golden-a", "golden-b"])
def test_golden_replays_roundtrip(name: str) -> None:
    replay = _golden(name)
    data = sharecode.encode(replay)
    assert sharecode.decode(data) == replay
    assert sharecode.from_text(sharecode.to_text(replay)) == replay
    # Deutlich kleiner als das JSON — das ist der Sinn des Formats.
    assert len(data) * 3 < len(json.dumps(replay.to_dict()))


def test_roundtrip_keeps_config_mode_and_label() -> None:
    replay = _record(CONFIG, 3, 900)
    restored = sharecode.decode(sharecode.encode(replay))
    assert restored == replay
    assert restored is not None
    assert restored.config.accessories == ("shield", "magnet")
    assert restored.mode is RunMode.DAILY
    assert restored.label == "2026-08-30"


def test_roundtrip_keeps_director_kind_and_version() -> None:
    # Ohne diese Felder käme ein adaptiver Free-Lauf als „konstant“ an und
    # fiele bei `headless.verify` durch.
    replay = replace(
        _record(CONFIG, 3, 300), director_kind=DirectorKind.ADAPTIVE, director_version=7
    )
    restored = sharecode.decode(sharecode.encode(replay))
    assert restored == replay
    assert restored is not None
    assert restored.director_kind is DirectorKind.ADAPTIVE
    assert restored.director_version == 7


def test_long_runs_and_edge_values_survive() -> None:
    base = _record(CONFIG, 5, 600)
    frames = ((0, 14), (15, 15), (5, 16), (2, 100_000), (8, 1))  # Grenzen des Escape-Bytes
    replay = replace(
        base,
        frames=frames,
        final=base.final._replace(tick=100_046, hp=-5, ammo=0, coins=1_000_000, shield=3),
    )
    restored = sharecode.decode(sharecode.encode(replay))
    assert restored is not None
    assert restored.frames == frames
    assert restored.final == replay.final
    assert list(restored.inputs())[:14] == [InputFrame.NONE] * 14


def test_text_is_url_safe_and_whitespace_tolerant() -> None:
    replay = _golden("golden-a")
    text = sharecode.to_text(replay)
    assert text.isascii()
    assert not set(text) - set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    wrapped = "\n".join(text[i : i + 40] for i in range(0, len(text), 40)) + "  \n"
    assert sharecode.from_text(wrapped) == replay


def test_decode_rejects_garbage() -> None:
    replay = _golden("golden-a")
    data = sharecode.encode(replay)
    assert sharecode.decode(b"") is None
    assert sharecode.decode(data[:-1]) is None  # Prüfsumme kaputt
    assert sharecode.decode(data[:-4]) is None  # abgeschnitten
    assert sharecode.decode(data + b"\x00") is None  # überzählige Bytes
    flipped = bytes([data[0] ^ 0x01]) + data[1:]
    assert sharecode.decode(flipped) is None
    assert sharecode.from_text("nicht base64!") is None
    assert sharecode.from_text("") is None


def test_decode_rejects_unknown_catalog_ids_and_versions() -> None:
    replay = _golden("golden-a")
    # Unbekanntes Schiff/Zubehör kann nicht über `RunConfig` entstehen — direkt im
    # Bytestrom patchen: Schiffsname steht als längenpräfixierter String hinter dem Seed.
    data = sharecode.encode(replay)
    body = bytearray(data[:-4])
    ship_start = 1 + 1 + 4 + 1  # Version, sim_version, seed, Längen-Byte
    body[ship_start : ship_start + len("Allrounder")] = b"Todesstern"
    assert sharecode.decode(_with_crc(bytes(body))) is None

    body = bytearray(data[:-4])
    body[0] = 99  # SHARECODE_VERSION
    assert sharecode.decode(_with_crc(bytes(body))) is None

    body = bytearray(data[:-4])
    body[ship_start + len("Allrounder")] = 3  # Modus-Byte (0/1 gültig)
    assert sharecode.decode(_with_crc(bytes(body))) is None

    body = bytearray(data[:-4])
    # Hinter Zubehör, Modus, Label und recorded_at (je ein Längen-Byte, da < 128 Zeichen).
    director_start = (
        ship_start
        + len("Allrounder")
        + 1
        + sum(1 + len(accessory) for accessory in replay.config.accessories)
        + 1
        + 1
        + len(replay.label)
        + 1
        + len(replay.recorded_at)
    )
    assert body[director_start] == 0  # golden-a: konstanter Director
    body[director_start] = 2  # Director-Byte (0/1 gültig)
    assert sharecode.decode(_with_crc(bytes(body))) is None


def _with_crc(body: bytes) -> bytes:
    import zlib

    return body + zlib.crc32(body).to_bytes(4, "big")
