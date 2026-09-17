# -*- coding: utf-8 -*-
import customtkinter as ctk
from pathlib import Path
from core.settings import Settings
from core.logger import get_logger
from core.app_paths import get_resource_dir

from .home_page import HomePage
from .versions_page import VersionsPage
from .settings_page import SettingsPage
from .logs_page import LogsPage
from .modpack_page import ModpackPage

logger = get_logger()

COLORS = {
    "bg": "#07111F",
    "sidebar": "#0A1728",
    "card": "#0D1D31",
    "hover": "#122A46",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
}

def _short_status(text: str, max_len: int = 48) -> str:
    t = str(text or "").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    head = max(12, max_len // 2 - 1)
    tail = max(10, max_len - head - 1)
    return t[:head] + "…" + t[-tail:]

class MainWindow(ctk.CTk):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.title("MtLauncher")
        self.geometry(
            f"{settings.get('window_width', 1100)}x{settings.get('window_height', 700)}"
        )
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg"])

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._set_window_icon()
        self.after(300, self._set_window_icon)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ----- 側邊欄 -----
        self.sidebar = ctk.CTkFrame(
            self, width=200, fg_color=COLORS["sidebar"], corner_radius=0
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="MtLauncher",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(25, 30))

        for text, cmd in [
            ("首頁", self.show_home),
            ("建立版本", self.show_versions),
            ("模組包", self.show_modpack),
            ("遊戲日誌", self.show_logs),
            ("設定", self.show_settings),
        ]:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                command=cmd,
                fg_color="transparent",
                hover_color=COLORS["hover"],
                anchor="w",
                height=40,
                font=ctk.CTkFont(size=14),
            ).pack(fill="x", padx=12, pady=4)

        self.bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", fill="x", padx=12, pady=12)

        self.status_label = ctk.CTkLabel(
            self.bottom_frame,
            text="就緒",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
            anchor="w",
            width=160,
            wraplength=160,
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        self.global_progress = ctk.CTkProgressBar(self.bottom_frame, height=6)
        self.global_progress.pack(fill="x", pady=(0, 8))
        self.global_progress.set(0)

        ctk.CTkLabel(
            self.bottom_frame,
            text="Made by Grok  ·  xAI",
            font=ctk.CTkFont(size=10),
            text_color="#64748B",
            anchor="w",
        ).pack(fill="x")

        # ----- 頂部狀態列 -----
        self.top_status = ctk.CTkFrame(
            self, fg_color="#0A1728", height=40, corner_radius=0
        )
        self.top_status.grid(row=0, column=1, sticky="ew")
        self.top_status.grid_propagate(False)

        self.top_status_label = ctk.CTkLabel(
            self.top_status,
            text="就緒 — 沒有進行中的下載",
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        self.top_status_label.pack(
            side="left", fill="x", expand=True, padx=(16, 8), pady=8
        )

        self.top_progress = ctk.CTkProgressBar(
            self.top_status, width=220, height=10
        )
        self.top_progress.pack(side="right", padx=16, pady=12)
        self.top_progress.set(0)

        # ----- 內容區 -----
        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.current_page = None
        self.show_home()

    def _set_window_icon(self):
        base = get_resource_dir()
        for rel in (
            Path("assets") / "icons" / "icon.ico",
            Path("assets") / "icon.ico",
        ):
            icon = base / rel
            if icon.exists():
                try:
                    self.iconbitmap(str(icon))
                except Exception:
                    pass
                break

    def set_status(self, text: str, progress: float = None):
        try:
            t = _short_status(text, 48)
            self.status_label.configure(text=t)
            self.top_status_label.configure(text=t)
            if progress is not None:
                p = max(0.0, min(1.0, float(progress)))
                self.global_progress.set(p)
                self.top_progress.set(p)
        except Exception:
            pass

    def clear_status(self):
        try:
            self.status_label.configure(text="就緒")
            self.top_status_label.configure(text="就緒 — 沒有進行中的下載")
            self.global_progress.set(0)
            self.top_progress.set(0)
        except Exception:
            pass

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def show_home(self):
        self._clear_content()
        page = HomePage(self.content, self.settings, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page

    def show_versions(self):
        self._clear_content()
        page = VersionsPage(self.content, self.settings, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page

    def show_modpack(self):
        self._clear_content()
        page = ModpackPage(self.content, self.settings, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page

    def show_logs(self):
        self._clear_content()
        page = LogsPage(self.content, self.settings, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page

    def show_settings(self):
        self._clear_content()
        page = SettingsPage(self.content, self.settings, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page