"""Local file cache for API responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class FileCache:
    """Simple file-based cache using content hashing."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, *args: str) -> str:
        content = "|".join(args)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, *args: str) -> str | None:
        path = self.cache_dir / f"{self._key(*args)}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("value")
        return None

    def set(self, *args: str, value: str) -> None:
        path = self.cache_dir / f"{self._key(*args)}.json"
        path.write_text(
            json.dumps({"args": args, "value": value}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def has(self, *args: str) -> bool:
        path = self.cache_dir / f"{self._key(*args)}.json"
        return path.exists()
