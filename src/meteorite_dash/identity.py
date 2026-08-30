"""Nostr-Identität: ein zufälliger Schlüssel pro Installation.

Der Schlüssel ist ein Pseudonym für geteilte Läufe, sonst nichts: 32 Byte aus
`secrets`, gespeichert als `identity.json` neben `progress.json` (Modus 0600,
wo das Dateisystem das kann). Ordner kopieren = Identität mitnehmen; Datei
verloren = neue Identität, die alten Läufe bleiben unter dem alten Pubkey.
Signaturen sind BIP-340-Schnorr über secp256k1 (`coincurve`), wie Nostr es
verlangt.
"""

import json
import logging
import os
import secrets
from pathlib import Path

from coincurve import PrivateKey, PublicKeyXOnly

from meteorite_dash.config import IDENTITY_FORMAT_VERSION, PUBKEY_SHORT_LEN

log = logging.getLogger(__name__)

SECRET_BYTES = 32


class Identity:
    def __init__(self, secret: bytes) -> None:
        if len(secret) != SECRET_BYTES:
            raise ValueError(f"Schlüssel braucht {SECRET_BYTES} Byte, hat {len(secret)}")
        self._key = PrivateKey(secret)  # ValueError, wenn der Skalar ungültig ist
        self.pubkey: str = PublicKeyXOnly.from_secret(secret).format().hex()

    @classmethod
    def generate(cls) -> "Identity":
        while True:
            try:
                return cls(secrets.token_bytes(SECRET_BYTES))
            except ValueError:  # praktisch unmöglich: Zufall außerhalb der Kurvenordnung
                continue

    @property
    def secret(self) -> bytes:
        return self._key.secret

    @property
    def short(self) -> str:
        return short_pubkey(self.pubkey)

    def sign(self, digest: bytes) -> bytes:
        """BIP-340-Signatur (64 Byte) über einen 32-Byte-Digest (die Event-ID)."""
        return self._key.sign_schnorr(digest)


def short_pubkey(pubkey: str) -> str:
    return pubkey[:PUBKEY_SHORT_LEN]


def verify_signature(pubkey: str, digest: bytes, signature: bytes) -> bool:
    try:
        return PublicKeyXOnly(bytes.fromhex(pubkey)).verify(signature, digest)
    except ValueError:
        return False


class IdentityStore:
    """Liest/schreibt den Schlüssel als JSON; fehlend oder kaputt -> neuer Schlüssel."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Identity | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Identität %s nicht lesbar: %s", self.path, exc)
            return None
        try:
            data: object = json.loads(raw)
        except ValueError as exc:
            log.warning("Identität %s ist kein gültiges JSON: %s", self.path, exc)
            return None
        identity = _from_dict(data)
        if identity is None:
            log.warning("Identität %s hat ein unbekanntes Format", self.path)
        return identity

    def save(self, identity: Identity) -> bool:
        payload = json.dumps(
            {"format": IDENTITY_FORMAT_VERSION, "secret": identity.secret.hex()}, indent=2
        )
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_path, self.path)
        except OSError as exc:
            log.warning("Identität %s nicht schreibbar: %s", self.path, exc)
            return False
        return True

    def load_or_create(self) -> Identity:
        identity = self.load()
        if identity is None:
            identity = Identity.generate()
            self.save(identity)
        return identity


def _from_dict(data: object) -> Identity | None:
    if not isinstance(data, dict):
        return None
    version = data.get("format")
    secret = data.get("secret")
    if isinstance(version, bool) or version != IDENTITY_FORMAT_VERSION:
        return None
    if not isinstance(secret, str):
        return None
    try:
        return Identity(bytes.fromhex(secret))
    except ValueError:
        return None
