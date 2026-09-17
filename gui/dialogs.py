# -*- coding: utf-8 -*-
import customtkinter as ctk
from pathlib import Path
from typing import Optional

COLORS = {
    "bg": "#0D1D31",
    "panel": "#07111F",
    "accent": "#3B82F6",
    "hover": "#2563EB",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
}

def _icon_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "icon.ico"

def _apply_icon(win):
    icon = _icon_path()
    if icon.exists():
        try:
            win.iconbitmap(str(icon))
        except Exception:
            pass

def _safe_parent(parent):
    try:
        if parent is not None and parent.winfo_exists():
            return parent
    except Exception:
        pass
    try:
        import tkinter as tk
        if tk._default_root is not None:
            return tk._default_root
    except Exception:
        pass
    return parent

class _BaseDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, width: int = 400, height: int = 180):
        parent = _safe_parent(parent)
        try:
            super().__init__(parent)
        except Exception:
            super().__init__()
        self.title(title)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)
        self.result = None
        _apply_icon(self)

        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - width) // 2
            y = py + (ph - height) // 2
        except Exception:
            x, y = 200, 200
        self.geometry(f"{width}x{height}+{x}+{y}")

        try:
            self.transient(parent.winfo_toplevel())
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.result = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

def show_info(parent, title: str, message: str):
    dlg = _BaseDialog(parent, title, 420, 220)
    ctk.CTkLabel(dlg, text=title, text_color=COLORS["accent"], font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(18, 6), anchor="w")
    ctk.CTkLabel(dlg, text=message, text_color=COLORS["text"], font=ctk.CTkFont(size=13), wraplength=380, justify="left").pack(padx=20, pady=(0, 12), anchor="w")

    def ok():
        dlg.result = True
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    ctk.CTkButton(dlg, text="確定", width=100, height=34, fg_color=COLORS["accent"], hover_color=COLORS["hover"], command=ok).pack(pady=(4, 16))
    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: ok())
    try:
        parent.wait_window(dlg)
    except Exception:
        dlg.wait_window()
    return dlg.result

def show_error(parent, title: str, message: str):
    dlg = _BaseDialog(parent, title, 420, 230)
    ctk.CTkLabel(dlg, text="⚠  " + title, text_color="#FCA5A5", font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(18, 6), anchor="w")
    ctk.CTkLabel(dlg, text=message, text_color=COLORS["text"], font=ctk.CTkFont(size=13), wraplength=380, justify="left").pack(padx=20, pady=(0, 12), anchor="w")

    def ok():
        dlg.result = True
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    ctk.CTkButton(dlg, text="確定", width=100, height=34, fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"], command=ok).pack(pady=(4, 16))
    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: ok())
    try:
        parent.wait_window(dlg)
    except Exception:
        dlg.wait_window()
    return dlg.result

def ask_yes_no(parent, title: str, message: str) -> bool:
    dlg = _BaseDialog(parent, title, 420, 220)
    ctk.CTkLabel(dlg, text=title, text_color=COLORS["text"], font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(18, 6), anchor="w")
    ctk.CTkLabel(dlg, text=message, text_color=COLORS["text_dim"], font=ctk.CTkFont(size=13), wraplength=380, justify="left").pack(padx=20, pady=(0, 16), anchor="w")
    bar = ctk.CTkFrame(dlg, fg_color="transparent")
    bar.pack(pady=(0, 16))

    def yes():
        dlg.result = True
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    def no():
        dlg.result = False
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    ctk.CTkButton(bar, text="取消", width=100, height=34, fg_color="#1E3A5F", hover_color="#122A46", command=no).pack(side="left", padx=8)
    ctk.CTkButton(bar, text="確定", width=100, height=34, fg_color=COLORS["accent"], hover_color=COLORS["hover"], command=yes).pack(side="left", padx=8)
    dlg.bind("<Escape>", lambda e: no())
    try:
        parent.wait_window(dlg)
    except Exception:
        dlg.wait_window()
    return bool(dlg.result)

def ask_string(parent, title: str, prompt: str, initial: str = "") -> Optional[str]:
    dlg = _BaseDialog(parent, title, 440, 240)
    ctk.CTkLabel(dlg, text=title, text_color=COLORS["accent"], font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(16, 4), anchor="w")
    ctk.CTkLabel(dlg, text=prompt, text_color=COLORS["text"], font=ctk.CTkFont(size=13), wraplength=400, justify="left").pack(padx=20, pady=(0, 8), anchor="w")
    entry = ctk.CTkEntry(dlg, width=400, height=36, fg_color=COLORS["panel"], border_color="#1E3A5F")
    entry.pack(padx=20, pady=4)
    if initial:
        entry.insert(0, initial)
        entry.select_range(0, "end")
    entry.focus_set()
    bar = ctk.CTkFrame(dlg, fg_color="transparent")
    bar.pack(pady=(16, 16))

    def ok():
        dlg.result = entry.get()
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    def cancel():
        dlg.result = None
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    ctk.CTkButton(bar, text="取消", width=100, height=34, fg_color="#1E3A5F", hover_color="#122A46", command=cancel).pack(side="left", padx=8)
    ctk.CTkButton(bar, text="確定", width=100, height=34, fg_color=COLORS["accent"], hover_color=COLORS["hover"], command=ok).pack(side="left", padx=8)
    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: cancel())
    try:
        parent.wait_window(dlg)
    except Exception:
        dlg.wait_window()
    return dlg.result