# -*- coding: utf-8 -*-
"""統一路徑：共用 .minecraft + versions 同層獨立實例"""
from pathlib import Path
from .settings import Settings

def get_minecraft_dir(settings: Settings) -> Path:
    d = settings.get_data_root() / ".minecraft"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_versions_dir(settings: Settings) -> Path:
    d = get_minecraft_dir(settings) / "versions"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_version_dir(settings: Settings, version_id: str) -> Path:
    d = get_versions_dir(settings) / version_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_libraries_dir(settings: Settings) -> Path:
    d = get_minecraft_dir(settings) / "libraries"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_assets_dir(settings: Settings) -> Path:
    d = get_minecraft_dir(settings) / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d