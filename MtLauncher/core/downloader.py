# -*- coding: utf-8 -*-
"""高速下載：少做 SHA1、高並行、鏡像、重試"""
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Callable, List, Tuple
import requests
from .logger import get_logger

logger = get_logger()

USE_MIRROR = True

MIRROR_REPLACEMENTS = [
    ("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven"),
    ("https://resources.download.minecraft.net", "https://bmclapi2.bangbang93.com/assets"),
    ("https://launcher.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://piston-meta.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://piston-data.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://launchermeta.mojang.com", "https://bmclapi2.bangbang93.com"),
]

DEFAULT_WORKERS = 48          # 小檔多：32~64；失敗變多就降到 24
CHUNK_SIZE = 1024 * 256
CONNECT_TIMEOUT = 6
READ_TIMEOUT = 20
MAX_RETRIES = 2
# 下載後是否強制校驗 SHA1（False = 更快；重要檔可在外層自行校驗）
VERIFY_SHA1_AFTER_DOWNLOAD = False

_thread_local = threading.local()

def mirror_url(url: str) -> str:
    if not USE_MIRROR or not url:
        return url
    for old, new in MIRROR_REPLACEMENTS:
        if url.startswith(old):
            return new + url[len(old):]
    return url

def _session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=DEFAULT_WORKERS,
            pool_maxsize=DEFAULT_WORKERS,
            max_retries=0,
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": "MtLauncher/1.0",
            "Connection": "keep-alive",
            "Accept-Encoding": "identity",
        })
        _thread_local.session = s
    return s

def _sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def _short_name(name: str, max_len: int = 28) -> str:
    name = str(name or "")
    if len(name) <= max_len:
        return name
    return name[:12] + "…" + name[-10:]

def _file_ok(path: Path, expected_sha1: Optional[str], expected_size: Optional[int]) -> bool:
    """快速判斷是否已下載完成：優先比 size，避免大量 SHA1"""
    if not path.exists():
        return False
    try:
        sz = path.stat().st_size
    except Exception:
        return False
    if sz <= 0:
        return False
    if expected_size is not None and sz != int(expected_size):
        return False
    # 有 size 且一致 → 視為 OK（快）
    if expected_size is not None:
        return True
    # 沒 size 才必要時算 sha1
    if expected_sha1:
        try:
            return _sha1_file(path).lower() == expected_sha1.lower()
        except Exception:
            return False
    return True

class Downloader:
    def __init__(self, workers: int = DEFAULT_WORKERS, use_mirror: bool = USE_MIRROR):
        self.workers = max(8, min(64, int(workers)))
        self.use_mirror = use_mirror

    def _url(self, url: str) -> str:
        return mirror_url(url) if self.use_mirror else url

    def download_file(
        self,
        url: str,
        dest: Path,
        expected_sha1: Optional[str] = None,
        progress_cb: Optional[Callable[[str, float], None]] = None,
        expected_size: Optional[int] = None,
    ) -> bool:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if _file_ok(dest, expected_sha1, expected_size):
            return True

        urls = []
        mirrored = self._url(url)
        if mirrored != url:
            urls.append(mirrored)
        urls.append(url)

        last_err = None
        for try_url in urls:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    if self._download_once(
                        try_url, dest, expected_sha1, expected_size, progress_cb
                    ):
                        return True
                except Exception as e:
                    last_err = e
                    logger.warning(f"retry {attempt}/{MAX_RETRIES} {dest.name}: {e}")
                    time.sleep(0.25 * attempt)
                    try:
                        dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
                    except Exception:
                        pass

        logger.warning(f"Download failed: {dest.name} ({last_err})")
        return False

    def _download_once(
        self,
        url: str,
        dest: Path,
        expected_sha1: Optional[str],
        expected_size: Optional[int],
        progress_cb: Optional[Callable[[str, float], None]],
    ) -> bool:
        tmp = dest.with_suffix(dest.suffix + ".part")
        s = _session()
        with s.get(
            url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        ) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            short = _short_name(dest.name, 20)
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(
                            f"{short} {done // 1024}KB",
                            min(0.99, done / total),
                        )

        if not tmp.exists() or tmp.stat().st_size <= 0:
            tmp.unlink(missing_ok=True)
            return False

        if expected_size is not None and tmp.stat().st_size != int(expected_size):
            tmp.unlink(missing_ok=True)
            raise IOError(f"size mismatch: {dest.name}")

        if VERIFY_SHA1_AFTER_DOWNLOAD and expected_sha1:
            if _sha1_file(tmp).lower() != expected_sha1.lower():
                tmp.unlink(missing_ok=True)
                raise IOError(f"SHA1 mismatch: {dest.name}")

        tmp.replace(dest)
        return True

    def download_many(
        self,
        tasks: List[Tuple],
        progress_cb: Optional[Callable[[str, float], None]] = None,
        label: str = "下載中",
    ) -> Tuple[int, int]:
        """
        tasks 支援：
          (url, dest, sha1)
          (url, dest, sha1, size)
        """
        if not tasks:
            return 0, 0

        pending = []
        for item in tasks:
            if len(item) >= 4:
                url, dest, sha1, size = item[0], item[1], item[2], item[3]
            else:
                url, dest, sha1 = item[0], item[1], item[2] if len(item) > 2 else None
                size = None
            dest = Path(dest)
            if _file_ok(dest, sha1, size):
                continue
            pending.append((url, dest, sha1, size))

        total = len(pending)
        if total == 0:
            if progress_cb:
                progress_cb(f"{label}（已快取）", 1.0)
            return 0, 0

        ok = fail = 0
        done = 0
        lock = threading.Lock()

        def one(item):
            url, dest, sha1, size = item
            success = self.download_file(
                url, dest, expected_sha1=sha1, expected_size=size
            )
            return dest.name, success

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(one, t): t for t in pending}
            for fut in as_completed(futs):
                name = "?"
                success = False
                try:
                    name, success = fut.result(timeout=READ_TIMEOUT * MAX_RETRIES + 40)
                except Exception as e:
                    logger.warning(f"task error: {e}")

                with lock:
                    done += 1
                    if success:
                        ok += 1
                    else:
                        fail += 1
                    if progress_cb:
                        progress_cb(
                            f"{label} {done}/{total}  {_short_name(name)}",
                            done / total,
                        )

        logger.info(f"{label}: {ok} ok, {fail} failed, need {total}")
        return ok, fail