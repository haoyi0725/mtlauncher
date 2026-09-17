# -*- coding: utf-8 -*-
"""
CurseForge 支援
需要使用者在設定中填入 API Key（可選）
若無 API Key，會嘗試使用公開端點（不保證穩定）
"""
import json
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Callable
import requests
from .logger import get_logger
from .downloader import Downloader

logger = get_logger()

CURSEFORGE_API = "https://api.curseforge.com/v1"

class CurseForgeClient:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip()
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key
        self.session.headers["User-Agent"] = "MtLauncher/1.0"
        self.downloader = Downloader()

    def get_file_info(self, project_id: int, file_id: int) -> Optional[Dict]:
        if not self.api_key:
            logger.warning("No CurseForge API Key, limited functionality")
            return None
        try:
            url = f"{CURSEFORGE_API}/mods/{project_id}/files/{file_id}"
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r.json().get("data")
        except Exception as e:
            logger.error(f"CurseForge get_file_info failed: {e}")
            return None

    def get_download_url(self, project_id: int, file_id: int) -> Optional[str]:
        info = self.get_file_info(project_id, file_id)
        if info:
            return info.get("downloadUrl")
        return None

    def download_mod(self, project_id: int, file_id: int, dest_dir: Path) -> bool:
        url = self.get_download_url(project_id, file_id)
        if not url:
            logger.error(f"Cannot get download URL for project={project_id} file={file_id}")
            return False
        # 檔名從 URL 或 info 取得
        filename = url.split("/")[-1].split("?")[0]
        dest = dest_dir / filename
        return self.downloader.download_file(url, dest)