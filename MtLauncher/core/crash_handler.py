# -*- coding: utf-8 -*-
import re
from pathlib import Path
from typing import Optional, Dict
from .logger import get_logger

logger = get_logger()

class CrashHandler:
    def __init__(self, mc_dir: Path):
        self.mc_dir = Path(mc_dir)

    def analyze(self, exit_code: int = -1) -> Dict:
        result = {
            "crashed": True,
            "exit_code": exit_code,
            "summary": "Minecraft 已結束",
            "possible_cause": "",
            "details": "",
            "crash_report": None,
            "latest_log": None,
        }

        # 尋找最新 crash-report
        crash_dir = self.mc_dir / "crash-reports"
        if crash_dir.exists():
            reports = sorted(crash_dir.glob("crash-*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if reports:
                result["crash_report"] = str(reports[0])
                content = reports[0].read_text(encoding="utf-8", errors="replace")
                result["details"] = content[:3000]
                result["possible_cause"] = self._analyze_text(content)

        # latest.log
        log_path = self.mc_dir / "logs" / "latest.log"
        if log_path.exists():
            result["latest_log"] = str(log_path)
            log_content = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
            if not result["possible_cause"]:
                result["possible_cause"] = self._analyze_text(log_content)
            if not result["details"]:
                result["details"] = log_content

        if exit_code != 0 and not result["possible_cause"]:
            result["possible_cause"] = f"程序以非零代碼結束 (Exit Code: {exit_code})"

        return result

    def _analyze_text(self, text: str) -> str:
        text_lower = text.lower()
        causes = []

        if "noclassdeffounderror" in text_lower or "classnotfoundexception" in text_lower:
            causes.append("缺少必要的 Library 或 Classpath 不完整")
        if "mixin" in text_lower:
            causes.append("Mixin 衝突（可能是某個 Mod 不相容）")
        if "outofmemoryerror" in text_lower or "java.lang.outofmemory" in text_lower:
            causes.append("記憶體不足，請增加最大 RAM")
        if "mod" in text_lower and ("incompatible" in text_lower or "failed to load" in text_lower):
            causes.append("Mod 載入失敗或版本不相容")
        if "fabric" in text_lower and "error" in text_lower:
            causes.append("Fabric 相關錯誤")
        if "forge" in text_lower or "neoforge" in text_lower:
            causes.append("Forge/NeoForge 相關錯誤")
        if "create" in text_lower:
            causes.append("可能與 Create 模組有關")

        # 擷取 Exception 行
        for line in text.splitlines():
            if "Exception" in line or "Error:" in line or "Caused by:" in line:
                causes.append(line.strip()[:120])
                break

        return "；".join(causes[:3]) if causes else "無法自動判斷原因，請查看完整日誌"