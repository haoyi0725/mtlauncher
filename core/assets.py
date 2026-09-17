# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional, Callable
import json
from .downloader import Downloader
from .logger import get_logger

logger = get_logger()

class AssetsDownloader:
    def __init__(self, mc_dir: Path):
        self.mc_dir = Path(mc_dir)
        self.assets_dir = self.mc_dir / "assets"
        self.downloader = Downloader()

    def download_assets(self, asset_index_id: str, progress_cb: Optional[Callable] = None) -> bool:
        index_path = self.assets_dir / "indexes" / f"{asset_index_id}.json"
        if not index_path.exists():
            logger.warning(f"Asset index not found: {index_path}")
            return False

        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        objects = index.get("objects", {})
        total = len(objects)
        objects_dir = self.assets_dir / "objects"
        objects_dir.mkdir(parents=True, exist_ok=True)

        for i, (name, info) in enumerate(objects.items()):
            if progress_cb and i % 50 == 0:
                progress_cb(f"Assets {i}/{total}", i / total if total else 0)

            hash_ = info["hash"]
            sub = hash_[:2]
            dest = objects_dir / sub / hash_
            if dest.exists():
                continue
            url = f"https://resources.download.minecraft.net/{sub}/{hash_}"
            self.downloader.download_file(url, dest, hash_)

        logger.info(f"Assets {asset_index_id} download finished")
        return True