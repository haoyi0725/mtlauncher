# -*- coding: utf-8 -*-
"""啟動器設定讀寫"""
import json
from pathlib import Path
from typing import Any

try:
    from .app_paths import get_app_dir, ensure_runtime_dirs
except Exception:
    def get_app_dir() -> Path:
        return Path(__file__).resolve().parent.parent

    def ensure_runtime_dirs() -> Path:
        data = get_app_dir() / "data"
        for d in (
            data,
            data / ".minecraft",
            data / ".minecraft" / "versions",
            data / ".minecraft" / "libraries",
            data / ".minecraft" / "assets",
            data / "runtimes",
            data / "logs",
            data / "skins",
        ):
            d.mkdir(parents=True, exist_ok=True)
        return data

DEFAULTS = {
    "player_name": "Steve",
    "min_ram": 2048,
    "max_ram": 4096,
    "java_path": "",
    "jvm_args": "",
    "mc_args": "",
    "window_width": 1100,
    "window_height": 700,
    "data_path": "",
    "custom_skin": "",  # 皮膚 png 路徑（可選）
}

class Settings:
    def __init__(self):
        ensure_runtime_dirs()
        self._data = dict(DEFAULTS)
        self.load()

    def get_data_root(self) -> Path:
        custom = ""
        if isinstance(self._data, dict):
            custom = str(self._data.get("data_path") or "").strip()
        if custom:
            p = Path(custom)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return ensure_runtime_dirs()

    def _settings_path(self) -> Path:
        return self.get_data_root() / "settings.json"

    def load(self):
        path = self._settings_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self._data[k] = v
            except Exception:
                pass

        for k, v in DEFAULTS.items():
            if k not in self._data:
                self._data[k] = v

        name = str(self._data.get("player_name") or "").strip()
        if not name:
            self._data["player_name"] = "Steve"

        try:
            self._data["min_ram"] = int(self._data.get("min_ram", 2048))
            self._data["max_ram"] = int(self._data.get("max_ram", 4096))
        except Exception:
            self._data["min_ram"] = 2048
            self._data["max_ram"] = 4096

        if not path.exists():
            self.save()

    def save(self) -> bool:
        path = self._settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            return self._data[key]
        if default is not None:
            return default
        return DEFAULTS.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, values: dict) -> None:
        if not isinstance(values, dict):
            return
        self._data.update(values)
        self.save()

    def get_all(self) -> dict:
        return dict(self._data)

    def reload(self) -> None:
        self._data = dict(DEFAULTS)
        self.load()