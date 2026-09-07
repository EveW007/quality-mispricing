from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class JsonFileCache:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        safe = "".join(character if character.isalnum() or character in "-_." else "_" for character in key)
        return self.directory / f"{safe}.json"

    def get(self, key: str, max_age: timedelta | None = None) -> Any | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        if max_age is not None:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if datetime.now(timezone.utc) - modified > max_age:
                return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, payload: Any) -> Path:
        destination = self.path_for(key)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.", suffix=".tmp", dir=self.directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, default=str)
                handle.write("\n")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination
