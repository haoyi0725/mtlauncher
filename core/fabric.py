# -*- coding: utf-8 -*-
"""
Fabric 安裝 → data/.minecraft/versions/<fabric-id>/
"""
import json
import requests
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any, Tuple
from .logger import get_logger
from .downloader import Downloader
from .minecraft import MinecraftInstaller

logger = get_logger()
FABRIC_META = "https://meta.fabricmc.net/v2"

class FabricInstaller:
    def __init__(self, mc_root: Path, mc_version: str, loader_version: str, display_name: str = ""):
        self.mc_root = Path(mc_root)
        self.mc_version = mc_version
        self.loader_version = loader_version
        self.display_name = display_name
        self.downloader = Downloader()

    @staticmethod
    def get_loader_versions(mc_version: str) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{FABRIC_META}/versions/loader/{mc_version}", timeout=20)
            r.raise_for_status()
            data = r.json()
            result = []
            for item in data:
                loader = item.get("loader", {})
                result.append({
                    "version": loader.get("version", ""),
                    "stable": loader.get("stable", False)
                })
            result.sort(key=lambda x: x["stable"], reverse=True)
            return result
        except Exception as e:
            logger.error(f"Fabric loaders fetch failed: {e}")
            return []

    def install(self, progress_cb: Optional[Callable] = None) -> Tuple[bool, str]:
        if progress_cb:
            progress_cb("安裝 Minecraft 原版...", 0.1)
        ok, _ = MinecraftInstaller(self.mc_root, self.mc_version).install(progress_cb)
        if not ok:
            return False, ""

        if progress_cb:
            progress_cb("下載 Fabric profile...", 0.5)

        profile_url = f"{FABRIC_META}/versions/loader/{self.mc_version}/{self.loader_version}/profile/json"
        try:
            r = requests.get(profile_url, timeout=30)
            r.raise_for_status()
            profile = r.json()
        except Exception as e:
            logger.error(f"Fabric profile failed: {e}")
            return False, ""

        version_id = profile.get("id") or f"fabric-loader-{self.loader_version}-{self.mc_version}"
        version_dir = self.mc_root / "versions" / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        with open(version_dir / f"{version_id}.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        if progress_cb:
            progress_cb("下載 Fabric libraries...", 0.7)

        libraries_dir = self.mc_root / "libraries"
        libs = profile.get("libraries", [])
        total = max(len(libs), 1)
        for i, lib in enumerate(libs):
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact and artifact.get("path") and artifact.get("url"):
                dest = libraries_dir / artifact["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    self.downloader.download_file(artifact["url"], dest)
            else:
                name = lib.get("name", "")
                url_base = lib.get("url", "https://maven.fabricmc.net/")
                if name.count(":") >= 2:
                    g, a, v = name.split(":")[:3]
                    path = f"{g.replace('.', '/')}/{a}/{v}/{a}-{v}.jar"
                    dest = libraries_dir / path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        self.downloader.download_file(url_base.rstrip("/") + "/" + path, dest)
            if progress_cb and i % 5 == 0:
                progress_cb(f"Fabric libs {i+1}/{total}", 0.7 + 0.25 * (i + 1) / total)

        (version_dir / "mods").mkdir(exist_ok=True)
        logger.info(f"Fabric installed: {version_id}")
        if progress_cb:
            progress_cb("Fabric 完成", 1.0)
        return True, version_id