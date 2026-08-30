"""Datei-Persistenz für den Spielfortschritt (Issue #14).

JSON statt `pickle`, defensiv geparst (siehe `Progress.from_dict`), atomar
geschrieben (Temp-Datei + `os.replace`). Eine fehlende oder kaputte Datei
liefert einen frischen Fortschritt; Schreibfehler werden gemeldet, nicht
geworfen — das Spiel läuft ohne Speicherstand weiter.
"""

import json
import logging
import os
import sys
from pathlib import Path

from meteorite_dash.config import SAVE_APP_DIR, SAVE_DIR_ENV, SAVE_FILENAME
from meteorite_dash.progress import Progress

log = logging.getLogger(__name__)


def default_save_dir() -> Path:
    """Nutzer-beschreibbares Datenverzeichnis; `SAVE_DIR_ENV` überschreibt es."""
    override = os.environ.get(SAVE_DIR_ENV)
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / SAVE_APP_DIR


def default_save_path() -> Path:
    """Pfad der Speicherdatei im Standard-Datenverzeichnis."""
    return default_save_dir() / SAVE_FILENAME


class SaveStore:
    """Liest und schreibt den `Progress` als JSON an einem festen Pfad."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Progress:
        """Liest den Fortschritt; fehlende oder kaputte Datei liefert einen frischen."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Progress()
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Speicherstand %s nicht lesbar: %s", self.path, exc)
            return Progress()
        try:
            data: object = json.loads(raw)
        except ValueError as exc:
            log.warning("Speicherstand %s ist kein gültiges JSON: %s", self.path, exc)
            return Progress()
        return Progress.from_dict(data)

    def save(self, progress: Progress) -> bool:
        """Schreibt atomar. False, wenn das Dateisystem nicht mitspielt."""
        payload = json.dumps(progress.to_dict(), indent=2, ensure_ascii=False)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, self.path)
        except OSError as exc:
            log.warning("Speicherstand %s nicht schreibbar: %s", self.path, exc)
            return False
        return True
