"""Share-Code: ein Replay als kompakte Bytes bzw. Text (Base64url).

Wire-Format für den Austausch von Läufen — Inhalt der Nostr-Events, später
auch QR-Code oder abgetippter Text. Kein Zustand, keine Simulation: `encode`
packt, `decode` entpackt defensiv (`None` statt Exception bei jedem
Formatfehler). Ob der Lauf echt ist, prüft danach `headless.verify`.

Layout (Big-Endian, Varints wie bei Protobuf, Strings mit Längen-Präfix):

    u8 SHARECODE_VERSION · u8 sim_version · u32 seed · str ship
    · u8 n + n x str accessory · u8 mode · str label · str recorded_at
    · u8 director_kind · u8 director_version
    · Snapshot (varint tick, svarint hp, svarint ammo, f64 light_years,
      varint coins, varint shield) · 32 B state_hash
    · varint n_events + n x (Maske << 4 | Länge; Länge 15 = Escape + varint)
    · u32 CRC-32 über alles davor

Ein Event kostet damit ein Byte, solange die Taste unter 15 Ticks gehalten
wird — echte Läufe brauchen ~3,5 Byte pro Spielsekunde.
"""

import base64
import binascii
import functools
import operator
import struct
import zlib

from meteorite_dash.config import SHARECODE_VERSION
from meteorite_dash.difficulty import DirectorKind
from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Frames, Replay, RunMode
from meteorite_dash.simulation import RunConfig, Snapshot

_ALL_INPUTS = int(functools.reduce(operator.or_, InputFrame))
_MODE_CODES: dict[RunMode, int] = {RunMode.FREE: 0, RunMode.DAILY: 1}
_MODES_BY_CODE: dict[int, RunMode] = {code: mode for mode, code in _MODE_CODES.items()}
_DIRECTOR_CODES: dict[DirectorKind, int] = {
    DirectorKind.CONSTANT: 0,
    DirectorKind.ADAPTIVE: 1,
    DirectorKind.RAMP: 2,
}
_DIRECTORS_BY_CODE: dict[int, DirectorKind] = {code: kind for kind, code in _DIRECTOR_CODES.items()}
_RUN_LENGTH_ESCAPE = 15  # Lauflängen ab hier stehen als Varint hinter dem Byte
_MAX_VARINT_BYTES = 10
_HASH_BYTES = 32
_CRC_BYTES = 4


class _Writer:
    def __init__(self) -> None:
        self.buf = bytearray()

    def u8(self, value: int) -> None:
        if not 0 <= value <= 0xFF:
            raise ValueError(f"u8 außerhalb des Bereichs: {value}")
        self.buf.append(value)

    def u32(self, value: int) -> None:
        self.buf += value.to_bytes(4, "big")  # OverflowError bei > 32 Bit

    def varint(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"varint darf nicht negativ sein: {value}")
        while True:
            chunk = value & 0x7F
            value >>= 7
            if value:
                self.buf.append(chunk | 0x80)
            else:
                self.buf.append(chunk)
                return

    def svarint(self, value: int) -> None:
        # ZigZag: 0, -1, 1, -2, ... -> 0, 1, 2, 3, ...
        self.varint(value * 2 if value >= 0 else -value * 2 - 1)

    def f64(self, value: float) -> None:
        self.buf += struct.pack(">d", value)

    def raw(self, data: bytes) -> None:
        self.buf += data

    def string(self, text: str) -> None:
        data = text.encode("utf-8")
        self.varint(len(data))
        self.buf += data


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, count: int) -> bytes:
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise ValueError("Share-Code endet zu früh")
        chunk = self.data[self.pos : end]
        self.pos = end
        return chunk

    def done(self) -> bool:
        return self.pos == len(self.data)

    def u8(self) -> int:
        return self.take(1)[0]

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "big")

    def varint(self) -> int:
        value = 0
        for shift in range(0, 7 * _MAX_VARINT_BYTES, 7):
            byte = self.u8()
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
        raise ValueError("Varint zu lang")

    def svarint(self) -> int:
        raw = self.varint()
        return raw // 2 if raw % 2 == 0 else -(raw + 1) // 2

    def f64(self) -> float:
        value: float = struct.unpack(">d", self.take(8))[0]
        return value

    def string(self) -> str:
        return self.take(self.varint()).decode("utf-8")


def encode(replay: Replay) -> bytes:
    writer = _Writer()
    writer.u8(SHARECODE_VERSION)
    writer.u8(replay.sim_version)
    writer.u32(replay.config.seed)
    writer.string(replay.config.ship)
    writer.u8(len(replay.config.accessories))
    for accessory in replay.config.accessories:
        writer.string(accessory)
    writer.u8(_MODE_CODES[replay.mode])
    writer.string(replay.label)
    writer.string(replay.recorded_at)
    writer.u8(_DIRECTOR_CODES[replay.director_kind])
    writer.u8(replay.director_version)
    final = replay.final
    writer.varint(final.tick)
    writer.svarint(final.hp)
    writer.svarint(final.ammo)
    writer.f64(final.light_years)
    writer.varint(final.coins)
    writer.varint(final.shield)
    writer.raw(bytes.fromhex(replay.state_hash))
    writer.varint(len(replay.frames))
    for mask, count in replay.frames:
        if count < _RUN_LENGTH_ESCAPE:
            writer.u8((mask << 4) | count)
        else:
            writer.u8((mask << 4) | _RUN_LENGTH_ESCAPE)
            writer.varint(count)
    writer.u32(zlib.crc32(bytes(writer.buf)))
    return bytes(writer.buf)


def decode(data: bytes) -> Replay | None:
    """`None` bei jedem Formatfehler — kaputte Prüfsumme, unbekannte Version,
    unbekanntes Schiff/Zubehör, ungültige Frames, überzählige Bytes."""
    if len(data) < _CRC_BYTES:
        return None
    body, crc = data[:-_CRC_BYTES], int.from_bytes(data[-_CRC_BYTES:], "big")
    if zlib.crc32(body) != crc:
        return None
    reader = _Reader(body)
    try:
        if reader.u8() != SHARECODE_VERSION:
            return None
        sim_version = reader.u8()
        seed = reader.u32()
        ship = reader.string()
        accessories = tuple(reader.string() for _ in range(reader.u8()))
        mode = _MODES_BY_CODE[reader.u8()]
        label = reader.string()
        recorded_at = reader.string()
        director_kind = _DIRECTORS_BY_CODE[reader.u8()]
        director_version = reader.u8()
        final = Snapshot(
            tick=reader.varint(),
            hp=reader.svarint(),
            ammo=reader.svarint(),
            light_years=reader.f64(),
            coins=reader.varint(),
            shield=reader.varint(),
        )
        state_hash = reader.take(_HASH_BYTES).hex()
        frames = _read_frames(reader)
        if not reader.done():
            return None
        config = RunConfig(seed, ship, accessories)  # ValueError bei unbekannten IDs
    except (ValueError, KeyError, struct.error):
        return None
    return Replay(
        config=config,
        frames=frames,
        final=final,
        state_hash=state_hash,
        sim_version=sim_version,
        recorded_at=recorded_at,
        mode=mode,
        label=label,
        director_kind=director_kind,
        director_version=director_version,
    )


def _read_frames(reader: _Reader) -> Frames:
    frames: list[tuple[int, int]] = []
    for _ in range(reader.varint()):
        byte = reader.u8()
        mask, count = byte >> 4, byte & 0x0F
        if count == _RUN_LENGTH_ESCAPE:
            count = reader.varint()
        if count <= 0 or mask & ~_ALL_INPUTS:
            raise ValueError("ungültiger Frame")
        frames.append((mask, count))
    return tuple(frames)


def to_text(replay: Replay) -> str:
    """Base64url ohne Padding — nur `A-Z a-z 0-9 - _`, sicher in JSON, URLs, Chats."""
    return base64.urlsafe_b64encode(encode(replay)).decode("ascii").rstrip("=")


def from_text(text: str) -> Replay | None:
    compact = "".join(text.split())
    padded = compact + "=" * (-len(compact) % 4)
    try:
        data = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return None
    return decode(data)
