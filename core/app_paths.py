# -*- coding: utf-8 -*-
"""開發模式 / 打包成 exe 後的路徑"""
import shutil
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """可寫入根目錄：exe 旁或專案根"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def get_resource_dir() -> Path:
    """唯讀資源（onefile 解壓目錄或專案根）"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return get_app_dir()

def _copy_default_pack_icon(data: Path) -> None:
    """
    自動把預設資源包圖示複製到 data/skins/pack.png
    來源優先：
      1. 打包資源 assets/skins/pack.png
      2. 專案 assets/skins/pack.png
    若目標已存在則不覆蓋（方便開發者之後手動替換 data 裡的檔）
    """
    dest = data / "skins" / "pack.png"
    if dest.exists():
        return

    candidates = [
        get_resource_dir() / "assets" / "skins" / "pack.png",
        get_app_dir() / "assets" / "skins" / "pack.png",
        get_resource_dir() / "assets" / "icons" / "pack.png",
        get_app_dir() / "assets" / "icons" / "pack.png",
    ]
    for src in candidates:
        if src.exists() and src.is_file():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            except Exception:
                pass
            break

def ensure_runtime_dirs() -> Path:
    """第一次開啟建立必要資料夾，並自動放置 pack.png"""
    root = get_app_dir()
    data = root / "data"
    for d in (
        data,
        data / ".minecraft",
        data / ".minecraft" / "versions",
        data / ".minecraft" / "libraries",
        data / ".minecraft" / "assets",
        data / "runtimes",
        data / "logs",
        data / "skins",
        data / "resourcepacks",
    ):
        d.mkdir(parents=True, exist_ok=True)

    # ★ 自動複製資源包圖示 → data/skins/pack.png
    _copy_default_pack_icon(data)

    settings_file = data / "settings.json"
    if not settings_file.exists():
        settings_file.write_text("{}", encoding="utf-8")

    return data