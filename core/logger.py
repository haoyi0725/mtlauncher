# -*- coding: utf-8 -*-
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger = None

def get_data_root() -> Path:
    """開發模式使用 ./data，正式可改成 %APPDATA%/MtLauncher"""
    # 可在 settings 中覆寫
    root = Path(os.environ.get("MTLAUNCHER_DATA", Path(__file__).parent.parent / "data"))
    root.mkdir(parents=True, exist_ok=True)
    return root

def setup_logger():
    global _logger
    if _logger is not None:
        return _logger

    log_dir = get_data_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mtlauncher.log"

    logger = logging.getLogger("MtLauncher")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    _logger = logger
    return logger

def get_logger():
    if _logger is None:
        return setup_logger()
    return _logger