# -*- coding: utf-8 -*-
"""原版 Minecraft 安裝 → data/.minecraft/versions/<id>/"""
import json
import platform
import requests
from pathlib import Path
from typing import Optional, Callable, Tuple, Dict, Any, List
from .logger import get_logger
from .downloader import Downloader

logger = get_logger()

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
LIB_BASE = "https://libraries.minecraft.net"

class MinecraftInstaller:
    def __init__(self, mc_root: Path, mc_version: str, display_name: str = ""):
        self.mc_root = Path(mc_root)
        self.mc_version = mc_version
        self.display_name = display_name or mc_version
        self.downloader = Downloader()

    def _fetch_version_json(self) -> Optional[Dict[str, Any]]:
        cache_dir = self.mc_root / "versions" / self.mc_version
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_json = cache_dir / f"{self.mc_version}.json"

        if local_json.exists():
            try:
                with open(local_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("id") or data.get("downloads") or data.get("libraries"):
                    return data
            except Exception:
                pass

        try:
            logger.info("Fetching version manifest...")
            r = requests.get(MANIFEST_URL, timeout=30)
            r.raise_for_status()
            manifest = r.json()
        except Exception as e:
            logger.error(f"Manifest fetch failed: {e}")
            return None

        entry = None
        for v in manifest.get("versions", []):
            if v.get("id") == self.mc_version:
                entry = v
                break
        if not entry:
            logger.error(f"Version {self.mc_version} not found in manifest")
            return None

        url = entry.get("url")
        if not url:
            return None

        try:
            logger.info(f"Downloading version json: {url}")
            r2 = requests.get(url, timeout=30)
            r2.raise_for_status()
            data = r2.json()
            with open(local_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        except Exception as e:
            logger.error(f"Version json download failed: {e}")
            return None

    def _maven_path(self, name: str) -> Optional[str]:
        parts = name.split(":")
        if len(parts) < 3:
            return None
        g, a, v = parts[0], parts[1], parts[2]
        classifier = parts[3] if len(parts) > 3 else None
        base = f"{g.replace('.', '/')}/{a}/{v}/{a}-{v}"
        if classifier:
            return f"{base}-{classifier}.jar"
        return f"{base}.jar"

    def _rules_allow(self, rules: Optional[List[Dict]]) -> bool:
        if not rules:
            return True
        allowed = False
        os_name = "windows" if platform.system() == "Windows" else (
            "osx" if platform.system() == "Darwin" else "linux"
        )
        for rule in rules:
            action = rule.get("action", "allow")
            os_rule = rule.get("os")
            match = True
            if os_rule and os_rule.get("name") and os_rule["name"] != os_name:
                match = False
            if not match:
                continue
            if action == "allow":
                allowed = True
            elif action == "disallow":
                allowed = False
        return allowed

    def install(self, progress_cb: Optional[Callable] = None) -> Tuple[bool, str]:
        self.mc_root.mkdir(parents=True, exist_ok=True)
        versions_dir = self.mc_root / "versions"
        libraries_dir = self.mc_root / "libraries"
        assets_dir = self.mc_root / "assets"
        for d in (versions_dir, libraries_dir, assets_dir):
            d.mkdir(exist_ok=True)

        version_id = self.mc_version
        version_dir = versions_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        if progress_cb:
            progress_cb("取得版本資訊...", 0.05)

        version_json = self._fetch_version_json()
        if not version_json:
            logger.error(f"Cannot get version json for {self.mc_version}")
            return False, version_id

        json_path = version_dir / f"{version_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(version_json, f, ensure_ascii=False, indent=2)

        # ----- client.jar -----
        if progress_cb:
            progress_cb("下載 client.jar...", 0.12)
        client = version_json.get("downloads", {}).get("client", {})
        client_url = client.get("url")
        client_sha = client.get("sha1")
        client_size = client.get("size")
        client_jar = version_dir / f"{version_id}.jar"
        if client_url:
            ok = self.downloader.download_file(
                client_url,
                client_jar,
                expected_sha1=client_sha,
                expected_size=client_size,
            )
            if not ok:
                logger.error("client.jar download failed")
                return False, version_id
        else:
            logger.warning("No client download url in version json")

        # ----- libraries（並行）-----
        if progress_cb:
            progress_cb("收集 libraries...", 0.2)

        lib_tasks: List[Tuple] = []
        os_name = "windows" if platform.system() == "Windows" else (
            "osx" if platform.system() == "Darwin" else "linux"
        )
        arch = "64"
        machine = platform.machine().lower()
        if machine in ("i386", "i686", "x86"):
            arch = "32"

        for lib in version_json.get("libraries", []):
            if not self._rules_allow(lib.get("rules")):
                continue

            downloads = lib.get("downloads") or {}
            artifact = downloads.get("artifact")

            if artifact and artifact.get("path"):
                dest = libraries_dir / artifact["path"]
                url = artifact.get("url") or f"{LIB_BASE}/{artifact['path']}"
                lib_tasks.append((
                    url, dest,
                    artifact.get("sha1"),
                    artifact.get("size"),
                ))
            else:
                name = lib.get("name", "")
                if name:
                    rel = self._maven_path(name)
                    if rel:
                        dest = libraries_dir / rel
                        url = f"{LIB_BASE}/{rel}"
                        lib_tasks.append((url, dest, None, None))

            classifiers = downloads.get("classifiers") or {}
            natives_map = lib.get("natives")
            want = None
            if natives_map and isinstance(natives_map, dict):
                c = natives_map.get(os_name)
                if c:
                    want = c.replace("${arch}", arch)

            for cname, cinfo in classifiers.items():
                if want and cname != want:
                    if not (cname.startswith("natives-") and os_name in cname):
                        continue
                elif want is None and natives_map:
                    if not (cname.startswith("natives-") and os_name in cname):
                        continue
                rel = cinfo.get("path")
                if not rel:
                    continue
                dest = libraries_dir / rel
                url = cinfo.get("url") or f"{LIB_BASE}/{rel}"
                lib_tasks.append((
                    url, dest,
                    cinfo.get("sha1"),
                    cinfo.get("size"),
                ))

            if natives_map and isinstance(natives_map, dict) and not classifiers:
                c = natives_map.get(os_name)
                if c:
                    c = c.replace("${arch}", arch)
                    name = lib.get("name", "")
                    parts = name.split(":")
                    if len(parts) >= 3:
                        nname = f"{parts[0]}:{parts[1]}:{parts[2]}:{c}"
                        rel = self._maven_path(nname)
                        if rel:
                            dest = libraries_dir / rel
                            url = f"{LIB_BASE}/{rel}"
                            lib_tasks.append((url, dest, None, None))

        def lib_cb(msg, pct):
            if progress_cb:
                progress_cb(msg, 0.2 + 0.35 * pct)

        self.downloader.download_many(lib_tasks, progress_cb=lib_cb, label="libraries")

        # ----- assets（並行 + size 快取）-----
        if progress_cb:
            progress_cb("下載 assets...", 0.55)
        self._download_assets(version_json, assets_dir, progress_cb)

        (version_dir / "mods").mkdir(exist_ok=True)
        if progress_cb:
            progress_cb("原版安裝完成", 1.0)
        logger.info(f"Minecraft {version_id} installed to {version_dir}")
        return True, version_id

    def _download_assets(
        self,
        version_json: Dict[str, Any],
        assets_dir: Path,
        progress_cb: Optional[Callable] = None,
    ):
        asset_index = version_json.get("assetIndex", {})
        idx_url = asset_index.get("url")
        idx_id = asset_index.get("id") or version_json.get("assets") or "legacy"
        if not idx_url:
            return

        indexes_dir = assets_dir / "indexes"
        objects_dir = assets_dir / "objects"
        indexes_dir.mkdir(parents=True, exist_ok=True)
        objects_dir.mkdir(parents=True, exist_ok=True)

        idx_path = indexes_dir / f"{idx_id}.json"
        if not idx_path.exists():
            if not self.downloader.download_file(idx_url, idx_path):
                logger.error("asset index download failed")
                return

        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception as e:
            logger.error(f"asset index read failed: {e}")
            return

        tasks: List[Tuple] = []
        for _name, info in index_data.get("objects", {}).items():
            h = info.get("hash", "")
            if len(h) < 2:
                continue
            sub = h[:2]
            dest = objects_dir / sub / h
            url = f"https://resources.download.minecraft.net/{sub}/{h}"
            size = info.get("size")
            # (url, dest, sha1, size) — size 用來快速跳過已下載檔
            tasks.append((url, dest, h, size))

        def assets_cb(msg, pct):
            if progress_cb:
                progress_cb(msg, 0.55 + 0.40 * pct)

        ok, fail = self.downloader.download_many(
            tasks, progress_cb=assets_cb, label="assets"
        )
        logger.info(f"Assets: {ok} ok, {fail} failed, total {len(tasks)}")