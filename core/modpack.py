# -*- coding: utf-8 -*-
"""CurseForge 模組包導入 → data/.minecraft/versions/<name>/"""
import json
import re
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Callable, Tuple
import requests
from .logger import get_logger
from .paths import get_minecraft_dir, get_versions_dir
from .minecraft import MinecraftInstaller
from .fabric import FabricInstaller
from .forge import ForgeInstaller
from .neoforge import NeoForgeInstaller
from .downloader import Downloader

logger = get_logger()

class ModpackImporter:
    def __init__(self, settings):
        self.settings = settings
        self.downloader = Downloader()

    def import_pack(
        self,
        zip_path: Path,
        progress_cb: Optional[Callable] = None
    ) -> Tuple[bool, str, str]:
        """
        回傳 (成功, 顯示名稱, 錯誤訊息)
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            return False, "", "檔案不存在"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                if progress_cb:
                    progress_cb("解壓模組包...", 0.05)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp_path)

                manifest_path = tmp_path / "manifest.json"
                if not manifest_path.exists():
                    # 有時在子資料夾
                    found = list(tmp_path.rglob("manifest.json"))
                    if found:
                        manifest_path = found[0]
                        tmp_path = manifest_path.parent
                    else:
                        return False, "", "找不到 manifest.json"

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                pack_name = manifest.get("name") or zip_path.stem
                mc_info = manifest.get("minecraft") or {}
                mc_version = mc_info.get("version") or ""
                loaders = mc_info.get("modLoaders") or []
                loader = "vanilla"
                loader_ver = ""
                for ld in loaders:
                    lid = (ld.get("id") or "").lower()
                    if lid.startswith("forge-"):
                        loader = "forge"
                        loader_ver = lid[6:]
                        break
                    if lid.startswith("neoforge-"):
                        loader = "neoforge"
                        loader_ver = lid[9:]
                        break
                    if lid.startswith("fabric-"):
                        loader = "fabric"
                        loader_ver = lid[7:]
                        break

                if not mc_version:
                    return False, pack_name, "manifest 缺少 minecraft.version"

                safe_name = re.sub(r'[<>:"/\\|?*]', "_", pack_name).strip().rstrip(". ")
                if not safe_name:
                    safe_name = "modpack"

                mc_root = get_minecraft_dir(self.settings)
                versions_dir = get_versions_dir(self.settings)
                if (versions_dir / safe_name).exists():
                    return False, pack_name, f"實例「{safe_name}」已存在"

                if progress_cb:
                    progress_cb(f"安裝 Minecraft {mc_version} + {loader}...", 0.15)

                if loader == "fabric":
                    ok, version_id = FabricInstaller(mc_root, mc_version, loader_ver, display_name=safe_name).install(progress_cb)
                elif loader == "forge":
                    ok, version_id = ForgeInstaller(mc_root, mc_version, loader_ver, display_name=safe_name).install(progress_cb)
                elif loader == "neoforge":
                    ok, version_id = NeoForgeInstaller(mc_root, mc_version, loader_ver, display_name=safe_name).install(progress_cb)
                else:
                    ok, version_id = MinecraftInstaller(mc_root, mc_version, display_name=safe_name).install(progress_cb)

                if not ok or not version_id:
                    return False, pack_name, "安裝遊戲/Loader 失敗"

                # 只改資料夾名
                final_id = version_id
                src = versions_dir / version_id
                dst = versions_dir / safe_name
                if src.exists() and version_id != safe_name and not dst.exists():
                    try:
                        src.rename(dst)
                        final_id = safe_name
                        logger.info(f"Renamed folder: {version_id} → {safe_name}")
                    except Exception as e:
                        logger.error(f"Rename failed: {e}")
                        final_id = version_id

                vdir = versions_dir / final_id
                vdir.mkdir(parents=True, exist_ok=True)
                mods_dir = vdir / "mods"
                mods_dir.mkdir(exist_ok=True)

                # 下載 manifest files（CurseForge API）
                files = manifest.get("files") or []
                total_f = max(len(files), 1)
                for i, fi in enumerate(files):
                    pid = fi.get("projectID")
                    fid = fi.get("fileID")
                    if not pid or not fid:
                        continue
                    if progress_cb:
                        progress_cb(f"下載模組 {i+1}/{total_f}...", 0.5 + 0.35 * (i + 1) / total_f)
                    try:
                        self._download_cf_file(int(pid), int(fid), mods_dir)
                    except Exception as e:
                        logger.warning(f"CF file {pid}/{fid} failed: {e}")

                # overrides
                overrides_name = manifest.get("overrides") or "overrides"
                overrides = tmp_path / overrides_name
                if overrides.exists():
                    if progress_cb:
                        progress_cb("套用 overrides...", 0.9)
                    for item in overrides.iterdir():
                        dest = vdir / item.name
                        if item.is_dir():
                            if dest.exists():
                                shutil.copytree(item, dest, dirs_exist_ok=True)
                            else:
                                shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)

                meta = {
                    "name": safe_name,
                    "mc_version": mc_version,
                    "loader": loader,
                    "loader_version": loader_ver,
                    "version_id": final_id,
                    "official_id": version_id,
                }
                with open(vdir / "mt_instance.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

                if progress_cb:
                    progress_cb("完成", 1.0)
                logger.info(f"Modpack imported: {safe_name} → {vdir}")
                return True, safe_name, ""
        except Exception as e:
            logger.exception("import_pack error")
            return False, "", str(e)

    def _download_cf_file(self, project_id: int, file_id: int, mods_dir: Path):
        # CurseForge 官方 API 需要 key；改用 mirror
        url = f"https://www.curseforge.com/api/v1/mods/{project_id}/files/{file_id}/download"
        # 備用：modrinth 不適用；使用 forgecdn
        meta_url = f"https://api.curseforge.com/v1/mods/{project_id}/files/{file_id}"
        # 無 API key 時用第三方 mirror（常見做法）
        dl = f"https://media.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/"
        # 更可靠：使用 edge.forgecdn 透過 scrape 困難，改試 curseforge 下載重定向
        try:
            # 使用 unofficial 端點
            r = requests.get(
                f"https://api.curse.tools/v1/cf/mods/{project_id}/files/{file_id}/download-url",
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                download_url = data.get("data") or data.get("url")
                if download_url:
                    filename = download_url.split("?")[0].rstrip("/").split("/")[-1]
                    dest = mods_dir / filename
                    if not dest.exists():
                        self.downloader.download_file(download_url, dest)
                    return
        except Exception as e:
            logger.warning(f"curse.tools failed: {e}")

        # fallback：空操作記錄
        logger.warning(f"Could not download CF mod {project_id}/{file_id}")