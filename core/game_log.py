# -*- coding: utf-8 -*-
"""遊戲即時日誌緩衝（啟動器 UI 共用）"""
from collections import deque
from threading import Lock
from typing import List

_lock = Lock()
_lines: deque = deque(maxlen=5000)
_listeners = []

def clear():
    with _lock:
        _lines.clear()

def append(line: str):
    if line is None:
        return
    text = str(line).rstrip()
    if not text:
        return
    with _lock:
        _lines.append(text)
        listeners = list(_listeners)
    for cb in listeners:
        try:
            cb(text)
        except Exception:
            pass

def get_all() -> List[str]:
    with _lock:
        return list(_lines)

def subscribe(callback):
    with _lock:
        if callback not in _listeners:
            _listeners.append(callback)

def unsubscribe(callback):
    with _lock:
        if callback in _listeners:
            _listeners.remove(callback)