# -*- coding: utf-8 -*-
"""收集 classpath 與 natives（支援新/舊 version JSON）"""
import platform
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .logger import get_logger
from .downloader import Downloader

logger = get_logger()
LIB_BASE = "https://libraries.minecraft.net"

def get_os_name() -> str:
    s = platform.system()
    if s == "Windows":
        return "windows"
    if s == "Darwin":
        return "osx"
    return "linux"

def _os_key() -> str:
    return get_os_name()

def _arch() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64"):
        return "64"
    if m in ("i386", "i686", "x86"):
        return "32"
    if m in ("aarch64", "arm64"):
        return "64"
    return "64"

def _rules_allow(rules, features=None) -> bool:
    if not rules:
        return True
    if isinstance(rules, dict):
        rules = [rules]

    allowed = False
    os_name = _os_key()
    features = features or {}

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        action = rule.get("action", "allow")
        os_rule = rule.get("os")
        feat_rule = rule.get("features")

        match = True
        if os_rule:
            if os_rule.get("name") and os_rule["name"] != os_name:
                match = False
        if feat_rule and match:
            for k, v in feat_rule.items():
                if features.get(k, False) != v:
                    match = False
                    break
        if not match:
            continue

        if action == "allow":
            allowed = True
        elif action == "disallow":
            allowed = False
    return allowed

def check_rule(rules, features=None) -> bool:
    """必須接受 2 個參數：check_rule(rule, features)"""
    return _rules_allow(rules, features)

def check_rules(rules, features=None) -> bool:
    return _rules_allow(rules, features)

def _maven_path(name: str) -> Optional[str]:
    parts = name.split(":")
    if len(parts) < 3:
        return None
    g, a, v = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    base = f"{g.replace('.', '/')}/{a}/{v}/{a}-{v}"
    if classifier:
        return f"{base}-{classifier}.jar"
    return f"{base}.jar"

def _ensure_lib(path_rel: str, libraries_dir: Path, url: Optional[str] = None) -> Optional[Path]:
    dest = libraries_dir / path_rel
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_url = url or f"{LIB_BASE}/{path_rel.replace(chr(92), '/')}"
    dl = Downloader()
    try:
        ok = dl.download_file(download_url, dest)
    except Exception as e:
        logger.warning(f"download_file error: {e}")
        ok = False
    if ok and dest.exists() and dest.stat().st_size > 0:
        return dest
    logger.warning(f"Failed to download library: {download_url}")
    return None

def _extract_natives(jar_path: Path, natives_dir: Path):
    natives_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(jar_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if name.endswith("/") or name.startswith("META-INF"):
                    continue
                lower = name.lower()
                if any(lower.endswith(ext) for ext in (".dll", ".so", ".dylib", ".jnilib")):
                    target = natives_dir / Path(name).name
                    if not target.exists():
                        with zf.open(info) as src, open(target, "wb") as out:
                            out.write(src.read())
    except Exception as e:
        logger.warning(f"Extract natives failed {jar_path}: {e}")

def collect_classpath_and_natives(
    version_json: Dict[str, Any],
    libraries_dir: Path,
    natives_dir: Path,
    client_jar: Optional[Path] = None
) -> Tuple[List[Path], List[str]]:
    libraries_dir = Path(libraries_dir)
    natives_dir = Path(natives_dir)
    natives_dir.mkdir(parents=True, exist_ok=True)

    paths: List[Path] = []
    errors: List[str] = []
    seen = set()

    def add_path(p: Optional[Path]):
        if p is None or not p.exists():
            return
        key = str(p.resolve()).lower()
        if key in seen:
            return
        seen.add(key)
        paths.append(p)

    os_name = _os_key()
    arch = _arch()

    for lib in version_json.get("libraries", []):
        if not _rules_allow(lib.get("rules")):
            continue

        downloads = lib.get("downloads") or {}
        artifact = downloads.get("artifact")

        if artifact and artifact.get("path"):
            rel = artifact["path"]
            url = artifact.get("url")
            p = _ensure_lib(rel, libraries_dir, url)
            if p:
                add_path(p)
            else:
                errors.append(f"Missing library: {libraries_dir / rel}")
        else:
            name = lib.get("name", "")
            if name:
                rel = _maven_path(name)
                if rel:
                    p = _ensure_lib(rel, libraries_dir)
                    if p:
                        add_path(p)
                    else:
                        errors.append(f"Missing library: {libraries_dir / rel}")

        classifiers = downloads.get("classifiers") or {}
        natives_map = lib.get("natives")

        want_classifier = None
        if natives_map and isinstance(natives_map, dict):
            c = natives_map.get(os_name)
            if c:
                want_classifier = c.replace("${arch}", arch)

        for cname, cinfo in classifiers.items():
            if want_classifier and cname != want_classifier:
                if not (cname.startswith("natives-") and os_name in cname):
                    continue
            elif want_classifier is None and natives_map:
                if not (cname.startswith("natives-") and os_name in cname):
                    continue
            rel = cinfo.get("path")
            url = cinfo.get("url")
            if rel:
                p = _ensure_lib(rel, libraries_dir, url)
                if p:
                    _extract_natives(p, natives_dir)
                else:
                    errors.append(f"Missing library: {libraries_dir / rel}")

        if natives_map and isinstance(natives_map, dict) and not classifiers:
            c = natives_map.get(os_name)
            if c:
                c = c.replace("${arch}", arch)
                name = lib.get("name", "")
                if name:
                    parts = name.split(":")
                    if len(parts) >= 3:
                        nname = f"{parts[0]}:{parts[1]}:{parts[2]}:{c}"
                        rel = _maven_path(nname)
                        if rel:
                            p = _ensure_lib(rel, libraries_dir)
                            if p:
                                _extract_natives(p, natives_dir)
                            else:
                                errors.append(f"Missing library: {libraries_dir / rel}")

    if client_jar is not None:
        if client_jar.exists():
            add_path(client_jar)
        else:
            errors.append(f"Missing client.jar: {client_jar}")

    return paths, errors

def build_classpath_string(paths: List[Path]) -> str:
    sep = ";" if platform.system() == "Windows" else ":"
    return sep.join(str(p.resolve()) for p in paths)