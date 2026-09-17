# -*- coding: utf-8 -*-
"""Minecraft 版本清單（正式 / 快照 / 遠古 / 愚人節）"""
import json
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from .logger import get_logger

logger = get_logger()

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

# 愚人節 / 特殊版本 id 關鍵字（不區分大小寫）
APRIL_FOOLS_PATTERNS = [
    r"w14a$",           # 15w14a 等
    r"w13a_or_b",
    r"w13oneblock",
    r"oneblockatatime",
    r"potato",
    r"infinite",
    r"pointless",
    r"combat.?test",    # 可選：戰鬥測試
    r"3d.?shareware",
    r"20w14infinite",
    r"22w13oneblockatatime",
    r"23w13a_or_b",
    r"24w14potato",
    r"25w14craftmine",
    r"2\.0",            # 2013 April Fools red/purple/blue
]

class VersionManager:
    def __init__(self, cache_path: Optional[Path] = None):
        self.manifest: Optional[Dict] = None
        self.cache_path = cache_path

    def fetch_manifest(self, force: bool = False) -> Dict:
        if self.manifest and not force:
            return self.manifest
        try:
            r = requests.get(MANIFEST_URL, timeout=30)
            r.raise_for_status()
            self.manifest = r.json()
            versions = self.manifest.get("versions", [])
            logger.info(f"Loaded {len(versions)} Minecraft versions")
            return self.manifest
        except Exception as e:
            logger.error(f"Failed to fetch version manifest: {e}")
            if self.cache_path and Path(self.cache_path).exists():
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.manifest = json.load(f)
                return self.manifest
            self.manifest = {"versions": []}
            return self.manifest

    def _is_april_fools(self, version_id: str) -> bool:
        low = version_id.lower()
        for pat in APRIL_FOOLS_PATTERNS:
            if re.search(pat, low):
                return True
        return False

    def classify(self, v: Dict[str, Any]) -> str:
        """
        回傳: release | snapshot | ancient | april_fools
        """
        vid = v.get("id", "")
        vtype = (v.get("type") or "").lower()
        if self._is_april_fools(vid):
            return "april_fools"
        if vtype in ("old_alpha", "old_beta"):
            return "ancient"
        if vtype == "snapshot":
            return "snapshot"
        if vtype == "release":
            return "release"
        # 其他少見 type 歸 snapshot
        return "snapshot"

    def get_versions(self, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        types: None = 全部
        或 ["release"], ["snapshot"], ["ancient"], ["april_fools"]
        也可傳官方 type: release / snapshot / old_alpha / old_beta
        """
        if not self.manifest:
            self.fetch_manifest()
        versions = list(self.manifest.get("versions", []))

        if not types:
            return versions

        types_set = set(t.lower() for t in types)
        result = []
        for v in versions:
            cat = self.classify(v)
            vtype = (v.get("type") or "").lower()
            if cat in types_set:
                result.append(v)
            elif vtype in types_set:
                result.append(v)
            elif "ancient" in types_set and vtype in ("old_alpha", "old_beta"):
                result.append(v)
        return result

    def get_version_json(self, version_id: str) -> Optional[Dict]:
        if not self.manifest:
            self.fetch_manifest()
        for v in self.manifest.get("versions", []):
            if v.get("id") == version_id:
                url = v.get("url")
                if not url:
                    return None
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                return r.json()
        return None