"""Tray preferences that survive restarts, stored as a small JSON file."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class JsonPreferences:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get_bool(self, name: str, default: bool) -> bool:
        value = self._read().get(name, default)
        return value if isinstance(value, bool) else default

    def set_bool(self, name: str, value: bool) -> None:
        data = self._read()
        data[name] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            log.warning("Ignoring unreadable preferences file %s", self._path)
            return {}
        return data if isinstance(data, dict) else {}
