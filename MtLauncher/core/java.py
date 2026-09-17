# -*- coding: utf-8 -*-
"""
Java 偵測、自動選擇、自動下載（Adoptium Temurin）
優先使用 version JSON 的 javaVersion.majorVersion
需要 Java 8 時不回退到 17/21
"""
import os
import re
import shutil
import subprocess
import platform
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Callable
import requests
from .logger import get_logger

logger = get_logger()

def get_runtimes_dir(data_root: Path) -> Path:
    d = Path(data_root) / "runtimes"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _run_java_version(java_path: str) -> Optional[str]:
    try:
        r = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        out = (r.stderr or r.stdout or "").strip()
        for line in out.splitlines():
            if "version" in line.lower():
                return line.strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None

def _parse_major_version(version_string: str) -> Optional[int]:
    if not version_string:
        return None
    m = re.search(r'version\s+"1\.(\d+)', version_string)
    if m:
        return int(m.group(1))
    m = re.search(r'version\s+"(\d+)', version_string)
    if m:
        return int(m.group(1))
    return None

def find_all_javas(extra_roots: Optional[List[Path]] = None) -> List[Dict]:
    candidates: List[str] = []
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        exe = "java.exe" if platform.system() == "Windows" else "java"
        candidates.append(str(Path(java_home) / "bin" / exe))
    path_java = shutil.which("java")
    if path_java:
        candidates.append(path_java)

    if platform.system() == "Windows":
        common_roots = [
            r"C:\Program Files\Eclipse Adoptium",
            r"C:\Program Files\Java",
            r"C:\Program Files\Microsoft",
            r"C:\Program Files\Zulu",
            r"C:\Program Files\Amazon Corretto",
            r"C:\Program Files\BellSoft",
            r"C:\Program Files\Oracle",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Eclipse Adoptium"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Temurin"),
        ]
        for base in common_roots:
            p = Path(base)
            if p.exists():
                for jdk in p.rglob("java.exe"):
                    if jdk.parent.name.lower() == "bin":
                        candidates.append(str(jdk))

    if extra_roots:
        for root in extra_roots:
            if root and Path(root).exists():
                exe_name = "java.exe" if platform.system() == "Windows" else "java"
                for jdk in Path(root).rglob(exe_name):
                    if jdk.parent.name.lower() == "bin":
                        candidates.append(str(jdk))

    results = []
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if not Path(cand).exists():
            continue
        ver_str = _run_java_version(cand)
        if not ver_str:
            continue
        major = _parse_major_version(ver_str)
        if major is None:
            continue
        results.append({"path": cand, "version_string": ver_str, "major": major})
        logger.info(f"Found Java {major}: {cand}")
    results.sort(key=lambda x: x["major"], reverse=True)
    return results

def find_java() -> Tuple[Optional[str], Optional[str]]:
    all_j = find_all_javas()
    if not all_j:
        return None, None
    return all_j[0]["path"], all_j[0]["version_string"]

def java_range_for_mc(mc_version: str) -> Tuple[int, int]:
    mc = (mc_version or "").strip().lower()
    if (
        mc.startswith("rd-")
        or mc.startswith("c0.")
        or mc.startswith("inf-")
        or mc.startswith("in-")
        or mc.startswith("a1.")
        or mc.startswith("b1.")
        or "classic" in mc
    ):
        return (8, 8)
    if re.match(r"^2[6-9]\.", mc) or re.match(r"^[3-9]\d\.", mc):
        return (21, 99)
    m = re.match(r"^1\.(\d+)(?:\.(\d+))?", mc)
    if not m:
        return (17, 21)
    minor = int(m.group(1))
    patch = int(m.group(2) or 0)
    if minor <= 16:
        return (8, 8)
    if minor < 20 or (minor == 20 and patch <= 4):
        return (17, 21)
    if minor == 20:
        return (21, 22)
    if minor == 21:
        return (21, 25)
    return (21, 99)

def required_java_major(mc_version: str) -> int:
    return java_range_for_mc(mc_version)[0]

def _adoptium_download_url(major: int) -> str:
    os_name = "windows" if platform.system() == "Windows" else (
        "mac" if platform.system() == "Darwin" else "linux"
    )
    arch = "x64"
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        arch = "aarch64"
    return (
        f"https://api.adoptium.net/v3/binary/latest/{major}/ga/"
        f"{os_name}/{arch}/jdk/hotspot/normal/eclipse?project=jdk"
    )

def download_java(
    major: int,
    data_root: Path,
    progress_cb: Optional[Callable[[str, float], None]] = None
) -> Optional[str]:
    runtimes = get_runtimes_dir(data_root)
    target_dir = runtimes / f"java-{major}"
    java_exe_name = "java.exe" if platform.system() == "Windows" else "java"

    existing = list(target_dir.rglob(java_exe_name))
    for p in existing:
        if p.parent.name.lower() == "bin":
            logger.info(f"Managed Java {major} already exists: {p}")
            return str(p)

    target_dir.mkdir(parents=True, exist_ok=True)
    url = _adoptium_download_url(major)
    archive_path = runtimes / (f"jdk-{major}.zip" if platform.system() == "Windows" else f"jdk-{major}.tar.gz")

    if progress_cb:
        progress_cb(f"下載 Java {major}...", 0.1)
    logger.info(f"Downloading Java {major} from {url}")

    try:
        with requests.get(url, stream=True, timeout=180, allow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total and progress_cb:
                        progress_cb(
                            f"下載 Java {major}... {done * 100 // total}%",
                            0.1 + 0.6 * done / total
                        )
    except Exception as e:
        logger.error(f"Download Java {major} failed: {e}")
        return None

    if progress_cb:
        progress_cb(f"解壓 Java {major}...", 0.75)
    try:
        if str(archive_path).endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(target_dir)
        else:
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(target_dir)
    except Exception as e:
        logger.error(f"Extract Java {major} failed: {e}")
        return None
    finally:
        try:
            archive_path.unlink(missing_ok=True)
        except Exception:
            pass

    for p in target_dir.rglob(java_exe_name):
        if p.parent.name.lower() == "bin":
            if progress_cb:
                progress_cb(f"Java {major} 就緒", 1.0)
            logger.info(f"Installed managed Java {major}: {p}")
            return str(p)
    logger.error(f"Java {major} extracted but java executable not found")
    return None

def select_java_for_version(
    mc_version: str,
    data_root: Path,
    preferred_path: str = "",
    instance_java: str = "",
    auto_download: bool = True,
    progress_cb: Optional[Callable[[str, float], None]] = None,
    required_major: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], int]:
    if required_major and required_major > 0:
        min_j = int(required_major)
        if min_j <= 8:
            max_j = 8
        elif min_j < 17:
            max_j = min_j
        else:
            max_j = 99
        logger.info(f"javaVersion from JSON: need major {min_j}~{max_j}")
    else:
        min_j, max_j = java_range_for_mc(mc_version)
        logger.info(f"MC {mc_version} Java range (fallback): {min_j} ~ {max_j}")

    if instance_java and Path(instance_java).exists():
        ver_str = _run_java_version(instance_java)
        major = _parse_major_version(ver_str or "") or 0
        logger.info(f"Using instance java_path (Java {major})")
        return instance_java, ver_str, major

    runtimes = get_runtimes_dir(data_root)
    all_j = find_all_javas(extra_roots=[runtimes])

    if preferred_path and Path(preferred_path).exists():
        ver_str = _run_java_version(preferred_path)
        major = _parse_major_version(ver_str or "")
        if major and min_j <= major <= max_j:
            return preferred_path, ver_str, major

    in_range = [j for j in all_j if min_j <= j["major"] <= max_j]
    if in_range:
        in_range.sort(key=lambda x: (abs(x["major"] - min_j), x["major"]))
        chosen = in_range[0]
        logger.info(f"Auto-selected Java {chosen['major']}: {chosen['path']}")
        return chosen["path"], chosen["version_string"], chosen["major"]

    # 遠古版（需要 8）禁止用 17/21 硬撐；直接下載
    allow_higher = min_j >= 17
    if allow_higher:
        higher = [j for j in all_j if j["major"] >= min_j]
        if higher:
            higher.sort(key=lambda x: x["major"])
            chosen = higher[0]
            logger.info(f"Auto-selected Java {chosen['major']} (>= {min_j}): {chosen['path']}")
            return chosen["path"], chosen["version_string"], chosen["major"]

    if auto_download:
        logger.info(f"No suitable Java in {min_j}~{max_j}, downloading Java {min_j}...")
        if progress_cb:
            progress_cb(f"自動下載 Java {min_j}（約 100MB）...", 0.05)
        path = download_java(min_j, data_root, progress_cb)
        if path:
            ver_str = _run_java_version(path)
            major = _parse_major_version(ver_str or "") or min_j
            return path, ver_str, major
        logger.error(f"Failed to download Java {min_j}")

    if all_j:
        best = all_j[0]
        logger.warning(f"Fallback Java {best['major']} (wanted {min_j}~{max_j})")
        return best["path"], best["version_string"], best["major"]
    return None, None, 0