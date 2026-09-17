# -*- coding: utf-8 -*-
"""
Minecraft 啟動器核心
- data/.minecraft/versions/<id>/
- gameDir = 版本資料夾
- Java 優先讀 version JSON 的 javaVersion.majorVersion
- @argfile 僅 Java 9+（Java 8 直接傳參數）
- 改名後仍可找到官方檔名的 client.jar
"""
import platform
import subprocess
import uuid
import hashlib
import json
from pathlib import Path
from typing import Optional, Callable, Dict
from .logger import get_logger
from .java import select_java_for_version, find_java
from .libraries import collect_classpath_and_natives, build_classpath_string
from .arguments import resolve_arguments
from .settings import Settings
from .paths import get_minecraft_dir, get_libraries_dir, get_assets_dir

logger = get_logger()

def offline_uuid(username: str) -> str:
    data = f"OfflinePlayer:{username}".encode("utf-8")
    h = bytearray(hashlib.md5(data).digest())
    h[6] = (h[6] & 0x0f) | 0x30
    h[8] = (h[8] & 0x3f) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))

def load_version_json(mc_dir: Path, version_id: str, _visited=None) -> Optional[Dict]:
    if _visited is None:
        _visited = set()
    if version_id in _visited:
        return None
    _visited.add(version_id)

    version_dir = mc_dir / "versions" / version_id
    if not version_dir.exists():
        logger.error(f"Version dir not found: {version_dir}")
        return None

    json_path = version_dir / f"{version_id}.json"
    if not json_path.exists():
        jsons = [j for j in version_dir.glob("*.json") if j.name != "mt_instance.json"]
        if not jsons:
            logger.error(f"No JSON found for version {version_id}")
            return None
        json_path = jsons[0]
        logger.info(f"Using version json: {json_path.name}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "inheritsFrom" in data:
        parent_id = data["inheritsFrom"]
        parent = load_version_json(mc_dir, parent_id, _visited)
        if parent is None:
            logger.error(f"Failed to load parent version: {parent_id}")
            return None
        merged = dict(parent)
        merged["libraries"] = parent.get("libraries", []) + data.get("libraries", [])
        p_args = parent.get("arguments", {})
        c_args = data.get("arguments", {})
        merged["arguments"] = {
            "jvm": list(p_args.get("jvm", [])) + list(c_args.get("jvm", [])),
            "game": list(p_args.get("game", [])) + list(c_args.get("game", []))
        }
        for k, v in data.items():
            if k not in ("libraries", "arguments", "inheritsFrom"):
                merged[k] = v
        return merged
    return data

def find_client_jar(mc_dir: Path, version_id: str) -> Path:
    version_dir = mc_dir / "versions" / version_id
    own = version_dir / f"{version_id}.jar"
    if own.exists() and own.stat().st_size > 100:
        return own

    if version_dir.exists():
        jars = [
            j for j in version_dir.glob("*.jar")
            if j.is_file() and j.stat().st_size > 100
        ]
        if jars:
            jsons = [j for j in version_dir.glob("*.json") if j.name != "mt_instance.json"]
            for jp in jsons:
                candidate = version_dir / f"{jp.stem}.jar"
                if candidate.exists() and candidate.stat().st_size > 100:
                    logger.info(f"Using jar matching json: {candidate}")
                    return candidate
            jars.sort(key=lambda p: p.stat().st_size, reverse=True)
            logger.info(f"Using jar in version folder: {jars[0]} ({jars[0].stat().st_size} bytes)")
            return jars[0]

        jsons = [j for j in version_dir.glob("*.json") if j.name != "mt_instance.json"]
        for jp in jsons:
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                parent_id = raw.get("inheritsFrom")
                if parent_id:
                    parent_dir = mc_dir / "versions" / parent_id
                    parent_jar = parent_dir / f"{parent_id}.jar"
                    if parent_jar.exists() and parent_jar.stat().st_size > 100:
                        logger.info(f"Using parent client.jar: {parent_jar}")
                        return parent_jar
                    if parent_dir.exists():
                        for j in parent_dir.glob("*.jar"):
                            if j.stat().st_size > 100:
                                logger.info(f"Using parent folder jar: {j}")
                                return j
            except Exception as e:
                logger.warning(f"parent jar lookup failed: {e}")

    logger.warning(f"No client.jar found for {version_id}")
    return own

def _mc_version_from_id(version_id: str) -> str:
    vid = version_id or ""
    for sep in ("-forge-", "-neoforge-", "-fabric-", "-quilt-"):
        if sep in vid.lower():
            return vid[:vid.lower().index(sep)]
    return vid

class Launcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.process = None

    def launch(
        self,
        version_id: str,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        mc_dir = get_minecraft_dir(self.settings)
        version_dir = mc_dir / "versions" / version_id
        libraries_dir = get_libraries_dir(self.settings)
        assets_dir = get_assets_dir(self.settings)

        version_json = load_version_json(mc_dir, version_id)
        if not version_json:
            if log_callback:
                log_callback(f"[錯誤] 無法載入版本: {version_id}")
            return False

        client_jar = find_client_jar(mc_dir, version_id)
        main_class = version_json.get("mainClass", "net.minecraft.client.main.Main")

        mc_ver_for_java = _mc_version_from_id(version_id)
        instance_java = ""
        meta = version_dir / "mt_instance.json"
        if meta.exists():
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    info = json.load(f)
                if info.get("official_id"):
                    mc_ver_for_java = info["official_id"]
                elif info.get("mc_version"):
                    mc_ver_for_java = info["mc_version"]
                instance_java = (info.get("java_path") or "").strip()
            except Exception:
                pass

        java_major = None
        jv = version_json.get("javaVersion") or {}
        if isinstance(jv, dict) and jv.get("majorVersion"):
            try:
                java_major = int(jv["majorVersion"])
            except Exception:
                java_major = None

        if log_callback:
            if java_major:
                log_callback(f"[Java] 此版本要求 Java {java_major}（version JSON）")
            else:
                log_callback(f"[Java] 未標註 javaVersion，依版本規則選擇（{mc_ver_for_java}）")

        def java_progress(msg, pct=0):
            if log_callback:
                log_callback(str(msg))

        java_path, ver_str, major = select_java_for_version(
            mc_ver_for_java,
            data_root=self.settings.get_data_root(),
            preferred_path=self.settings.get("java_path", ""),
            instance_java=instance_java,
            auto_download=True,
            progress_cb=java_progress,
            required_major=java_major,
        )
        if not java_path:
            java_path, ver_str = find_java()
            major = 0
            if not java_path:
                if log_callback:
                    log_callback("[錯誤] 找不到 Java")
                return False

        if log_callback:
            log_callback(f"[Java] 使用 Java {major}: {java_path}")
            if ver_str:
                log_callback(f"[Java] {ver_str}")

        natives_dir = version_dir / "natives"
        natives_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "mods").mkdir(exist_ok=True)

        is_mod_launcher = (
            "bootstraplauncher" in (main_class or "").lower()
            or "forgebootstrap" in (main_class or "").lower()
        )
        vid_check = (version_json.get("id") or version_id).lower()
        if "neoforge" in vid_check or (
            "forge" in vid_check and "fabric" not in vid_check and "quilt" not in vid_check
        ):
            is_mod_launcher = True
        if "neoforge" in version_id.lower() or (
            "forge" in version_id.lower() and "fabric" not in version_id.lower()
        ):
            is_mod_launcher = True

        if is_mod_launcher:
            classpath_paths, errors = collect_classpath_and_natives(
                version_json, libraries_dir, natives_dir, client_jar=None
            )
            logger.info("ModLauncher detected - skipping vanilla client.jar on classpath")
        else:
            if not client_jar.exists():
                if log_callback:
                    log_callback(f"[錯誤] 找不到 client.jar: {client_jar}")
                return False
            classpath_paths, errors = collect_classpath_and_natives(
                version_json, libraries_dir, natives_dir, client_jar
            )
            logger.info(f"client.jar = {client_jar}")

        for e in errors:
            logger.warning(e)

        if not classpath_paths:
            if log_callback:
                log_callback("[錯誤] classpath 為空")
            return False

        classpath = build_classpath_string(classpath_paths)
        logger.info(f"Classpath length: {len(classpath_paths)} jars")

        player = self.settings.get("player_name", "Steve")
        sep = ";" if platform.system() == "Windows" else ":"
        game_dir = str(version_dir.resolve())

        asset_index = "legacy"
        if isinstance(version_json.get("assetIndex"), dict):
            asset_index = version_json["assetIndex"].get("id", "legacy")
        elif version_json.get("assets"):
            asset_index = version_json.get("assets", "legacy")

        placeholders = {
            "auth_player_name": player,
            "version_name": version_id,
            "game_directory": game_dir,
            "assets_root": str(assets_dir.resolve()),
            "assets_index_name": asset_index,
            "auth_uuid": offline_uuid(player),
            "auth_access_token": "0",
            "user_type": "legacy",
            "version_type": version_json.get("type", "release"),
            "natives_directory": str(natives_dir.resolve()),
            "launcher_name": "MtLauncher",
            "launcher_version": "1.0",
            "classpath": classpath,
            "library_directory": str(libraries_dir.resolve()).replace("\\", "/"),
            "classpath_separator": sep,
        }

        jvm_args, game_args = resolve_arguments(version_json, placeholders)

        def clean(a: str) -> str:
            for k, v in placeholders.items():
                a = a.replace(f"${{{k}}}", str(v))
            return a

        jvm_args = [clean(str(a)) for a in jvm_args]
        game_args = [clean(str(a)) for a in game_args]

        min_ram = self.settings.get("min_ram", 2048)
        max_ram = self.settings.get("max_ram", 4096)
        custom_jvm = [x for x in self.settings.get("jvm_args", "").strip().split() if x]
        custom_mc = [x for x in self.settings.get("mc_args", "").strip().split() if x]

        args = []
        args += [f"-Xms{min_ram}M", f"-Xmx{max_ram}M"]
        args += custom_jvm
        args += jvm_args
        if not any("java.library.path" in a for a in args):
            args.append(f"-Djava.library.path={natives_dir.resolve()}")

        has_module_path = any(
            isinstance(a, str) and (a == "-p" or a.startswith("-p ") or a.startswith("-p/"))
            for a in args
        )
        if not has_module_path and classpath:
            args += ["-cp", classpath]

        args.append(main_class)
        args += game_args
        args += custom_mc
        args = [clean(str(a)) for a in args]

        if log_callback:
            log_callback(f"[啟動] {player} @ {version_id}")
            log_callback(f"[gameDir] {game_dir}")
            log_callback(f"[mainClass] {main_class}")
            log_callback(f"[client.jar] {client_jar} exists={client_jar.exists()}")

        try:
            # @argfile 僅 Java 9+；Java 8 必須直接傳參數
            use_argfile = platform.system() == "Windows" and int(major or 0) >= 9

            if use_argfile:
                argfile = version_dir / "mtlauncher_args.txt"
                with open(argfile, "w", encoding="utf-8", errors="surrogatepass") as f:
                    for a in args:
                        if " " in a or "\t" in a or any(ord(c) > 127 for c in a):
                            escaped = a.replace("\\", "\\\\").replace('"', '""')
                            f.write(f'"{escaped}"\n')
                        else:
                            f.write(a + "\n")
                cmd = [java_path, f"@{argfile}"]
                logger.info(f"Using argfile: {argfile}")
            else:
                cmd = [java_path] + args
                logger.info(f"Launch without argfile (Java {major})")

            if log_callback:
                log_callback(f"[cmd] java major={major}, argfile={use_argfile}, args={len(args)}")

            flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            self.process = subprocess.Popen(
                cmd,
                cwd=game_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                bufsize=1
            )

            if log_callback and self.process.stdout:
                for line in self.process.stdout:
                    line = line.rstrip()
                    if line:
                        log_callback(line)

            ret = self.process.wait()
            if log_callback:
                log_callback(f"[結束] Exit code: {ret}")
            return ret == 0
        except Exception as e:
            logger.exception("Launch failed")
            if log_callback:
                log_callback(f"[錯誤] {e}")
            return False