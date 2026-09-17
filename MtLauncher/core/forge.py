# -*- coding: utf-8 -*-
"""
Forge 安裝 → data/.minecraft/versions/<forge-id>/
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
FORGE_MAVEN = "https://maven.minecraftforge.net"
FORGE_METADATA = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"

class ForgeInstaller:
    def __init__(self, mc_root: Path, mc_version: str, forge_version: str, display_name: str = ""):
        self.mc_root = Path(mc_root)
        self.mc_version = mc_version
        self.forge_version = forge_version
        self.display_name = display_name
        self.downloader = Downloader()

    @staticmethod
    def get_forge_versions(mc_version: str) -> List[str]:
        try:
            r = requests.get(FORGE_METADATA, timeout=20)
            r.raise_for_status()
            versions = re.findall(r"<version>([^<]+)</version>", r.text)
            matched = []
            for v in versions:
                if v.startswith(mc_version + "-"):
                    matched.append(v[len(mc_version) + 1:])
            matched = sorted(set(matched), reverse=True)
            logger.info(f"Forge for {mc_version}: {len(matched)} versions")
            return matched
        except Exception as e:
            logger.error(f"Forge versions failed: {e}")
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
            if not d.is_dir():
                continue
            n = d.name.lower()
            if "forge" in n and "neoforge" not in n:
                if self.forge_version in d.name or self.mc_version in d.name:
                    return d.name
        return None

    def install(self, progress_cb: Optional[Callable] = None) -> Tuple[bool, str]:
        if progress_cb:
            progress_cb("安裝 Minecraft 原版...", 0.1)
        ok, _ = MinecraftInstaller(self.mc_root, self.mc_version).install(progress_cb)
        if not ok:
            return False, ""

        self._ensure_profiles()

        full_ver = self.forge_version
        if not full_ver.startswith(self.mc_version):
            full_ver = f"{self.mc_version}-{self.forge_version}"

        if progress_cb:
            progress_cb("下載 Forge Installer...", 0.35)

        installer_name = f"forge-{full_ver}-installer.jar"
        installer_url = f"{FORGE_MAVEN}/net/minecraftforge/forge/{full_ver}/{installer_name}"
        installer_path = self.mc_root / "libraries" / "net" / "minecraftforge" / "forge" / full_ver / installer_name
        installer_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.downloader.download_file(installer_url, installer_path):
            logger.error(f"Forge installer download failed: {installer_url}")
            return False, ""

        # 用適合的 Java 跑 installer
        from .settings import Settings
        # 簡化：用 find / select
        data_root = self.mc_root.parent
        java_path, _, _ = select_java_for_version(
            self.mc_version, data_root=data_root, auto_download=True,
            progress_cb=progress_cb
        )
        if not java_path:
            java_path, _ = find_java()
        if not java_path:
            logger.error("No Java for Forge installer")
            return False, ""

        if progress_cb:
            progress_cb("執行 Forge Installer...", 0.5)

        cmd = [java_path, "-jar", str(installer_path), "--installClient", str(self.mc_root)]
        try:
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(
                cmd, cwd=str(self.mc_root),
                capture_output=True, text=True, timeout=600, creationflags=flags
            )
            if result.returncode != 0:
                logger.error(f"Forge installer failed:\n{result.stdout}\n{result.stderr}")
                return False, ""
            logger.info("Forge installer OK")
        except Exception as e:
            logger.error(f"Forge installer exception: {e}")
            return False, ""

        version_id = self._find_installed() or f"{self.mc_version}-forge-{self.forge_version}"
        vdir = self.mc_root / "versions" / version_id
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "mods").mkdir(exist_ok=True)

        if progress_cb:
            progress_cb("Forge 完成", 1.0)
        logger.info(f"Forge installed: {version_id}")
        return True, version_id