# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Storage backend abstraction for settings persistence."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from config import Config


class StorageBackend(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        ...

    @abstractmethod
    def remove(self, key: str) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def contains(self, key: str) -> bool:
        ...

    @abstractmethod
    def sync(self) -> None:
        ...


class JsonStorageBackend(StorageBackend):
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Config.SETTINGS_FILE
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _resolve(self, key: str) -> tuple[dict[str, Any], str]:
        parts = key.split("/")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        return node, parts[-1]

    def get(self, key: str, default: Any = None) -> Any:
        node, leaf = self._resolve(key)
        return node.get(leaf, default)

    def set(self, key: str, value: Any) -> None:
        node, leaf = self._resolve(key)
        node[leaf] = value
        self._save()

    def remove(self, key: str) -> None:
        node, leaf = self._resolve(key)
        node.pop(leaf, None)
        self._save()

    def clear(self) -> None:
        self._data = {}
        self._save()

    def contains(self, key: str) -> bool:
        node, leaf = self._resolve(key)
        return leaf in node

    def sync(self) -> None:
        self._save()