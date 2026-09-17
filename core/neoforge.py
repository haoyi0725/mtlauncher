# -*- coding: utf-8 -*-
"""
NeoForge 安裝 → data/.minecraft/versions/<neoforge-id>/
"""
import re
import json
import subprocess
import platform
from pathlib import Path
from typing import List, Optional, Callable, Tuple
import requests
from .logger import get_logger
from .downloader import Downloader
from .minecraft import MinecraftInstaller
from .java import find_java, select_java_for_version

logger = get_logger()
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases"
NEOFORGE_METADATA = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"

class NeoForgeInstaller:
    def __init__(self, mc_root: Path, mc_version: str, neoforge_version: str, display_name: str = ""):
        self.mc_root = Path(mc_root)
        self.mc_version = mc_version
        self.neoforge_version = neoforge_version
        self.display_name = display_name
        self.downloader = Downloader()

    @staticmethod
    def _version_key(v: str) -> Tuple:
        main, _, suffix = v.partition("-")
        parts = []
        for p in main.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 4:
            parts.append(0)
        suffix_order = 4
        if suffix:
            low = suffix.lower()
            if "beta" in low:
                suffix_order = 1
            elif "rc" in low:
                suffix_order = 2
            else:
                suffix_order = 3
        return (parts[0], parts[1], parts[2], parts[3], suffix_order, suffix)

    @staticmethod
    def get_neoforge_versions(mc_version: str) -> List[str]:
        try:
            r = requests.get(NEOFORGE_METADATA, timeout=20)
            r.raise_for_status()
            all_versions = re.findall(r"<version>([^<]+)</version>", r.text)
            if mc_version.startswith("1."):
                parts = mc_version.split(".")
                prefix = f"{parts[1]}.{parts[2]}" if len(parts) >= 3 else parts[1] + ".0"
            else:
                prefix = mc_version
            matched = [
                v for v in all_versions
                if v.startswith(prefix + ".") or v.startswith(prefix + "-") or v == prefix
            ]
            matched = sorted(set(matched), key=NeoForgeInstaller._version_key, reverse=True)
            logger.info(f"NeoForge for {mc_version}: {len(matched)}")
            return matched
        except Exception as e:
            logger.error(f"NeoForge versions failed: {e}")
            return []

    def _ensure_profiles(self):
        path = self.mc_root / "launcher_profiles.json"
        if path.exists():
            return
        data = {
            "profiles": {
                "MtLauncher": {
                    "name": "MtLauncher",
                    "type": "custom",
                    "lastVersionId": self.mc_version,
                    "gameDir": str(self.mc_root)
                }
            },
            "selectedProfile": "MtLauncher",
            "clientToken": "mtlauncher",
            "launcherVersion": {"name": "MtLauncher", "format": 21, "profilesFormat": 2}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _find_installed(self) -> Optional[str]:
        versions_dir = self.mc_root / "versions"
        if not versions_dir.exists():
            return None
        for d in versions_dir.iterdir():
            if d.is_dir() and "neoforge" in d.name.lower():
                if self.neoforge_version in d.name or self.mc_version in d.name:
                    return d.name
        return None

    def install(self, progress_cb: Optional[Callable] = None) -> Tuple[bool, str]:
        if progress_cb:
            progress_cb("安裝 Minecraft 原版...", 0.1)
        ok, _ = MinecraftInstaller(self.mc_root, self.mc_version).install(progress_cb)
        if not ok:
            return False, ""

        self._ensure_profiles()

        full_ver = self.neoforge_version
        if progress_cb:
            progress_cb("下載 NeoForge Installer...", 0.35)

        installer_name = f"neoforge-{full_ver}-installer.jar"
        installer_url = f"{NEOFORGE_MAVEN}/net/neoforged/neoforge/{full_ver}/{installer_name}"
        installer_path = (
            self.mc_root / "libraries" / "net" / "neoforged" / "neoforge" / full_ver / installer_name
        )
        installer_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.downloader.download_file(installer_url, installer_path):
            logger.error(f"NeoForge installer download failed")
            return False, ""

        data_root = self.mc_root.parent
        java_path, _, _ = select_java_for_version(
            self.mc_version, data_root=data_root, auto_download=True, progress_cb=progress_cb
        )
        if not java_path:
            java_path, _ = find_java()
        if not java_path:
            return False, ""

        if progress_cb:
            progress_cb("執行 NeoForge Installer...", 0.5)

        cmd = [java_path, "-jar", str(installer_path), "--installClient", str(self.mc_root)]
        try:
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(
                cmd, cwd=str(self.mc_root),
                capture_output=True, text=True, timeout=600, creationflags=flags
            )
            if result.returncode != 0:
                logger.error(f"NeoForge installer failed:\n{result.stdout}\n{result.stderr}")
                return False, ""
        except Exception as e:
            logger.error(f"NeoForge installer exception: {e}")
            return False, ""

        version_id = self._find_installed() or f"{self.mc_version}-neoforge-{self.neoforge_version}"
        vdir = self.mc_root / "versions" / version_id
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "mods").mkdir(exist_ok=True)

        if progress_cb:
            progress_cb("NeoForge 完成", 1.0)
        logger.info(f"NeoForge installed: {version_id}")
        return True, version_id