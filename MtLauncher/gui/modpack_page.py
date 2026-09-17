# -*- coding: utf-8 -*-
import customtkinter as ctk
import threading
from pathlib import Path
from tkinter import filedialog
from gui.dialogs import show_info, show_error
from core.modpack import ModpackImporter
from core.logger import get_logger

logger = get_logger()

COLORS = {
    "bg": "#07111F",
    "card": "#0D1D31",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
}

class ModpackPage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.settings = settings
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self, text="模組包",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        form = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        form.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form,
            text="導入 CurseForge 模組包 ZIP（含 manifest.json）",
            text_color=COLORS["text"],
            justify="left"
        ).pack(anchor="w", padx=15, pady=(15, 8))

        self.progress_label = ctk.CTkLabel(form, text="", text_color=COLORS["text_dim"])
        self.progress_label.pack(anchor="w", padx=15, pady=4)
        self.progress_bar = ctk.CTkProgressBar(form)
        self.progress_bar.pack(fill="x", padx=15, pady=4)
        self.progress_bar.set(0)

        self.import_btn = ctk.CTkButton(
            form, text="選擇 ZIP 並導入", fg_color=COLORS["accent"], height=40,
            command=self.import_pack
        )
        self.import_btn.pack(fill="x", padx=15, pady=15)

    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _set_progress(self, msg: str, pct: float = 0):
        def update():
            try:
                if self.winfo_exists():
                    self.progress_label.configure(text=msg)
                    self.progress_bar.set(max(0.0, min(1.0, float(pct))))
                if hasattr(self.main_window, "set_status"):
                    self.main_window.set_status(msg, pct)
            except Exception:
                pass
        self._ui(update)

    def import_pack(self):
        path = filedialog.askopenfilename(
            title="選擇 CurseForge 模組包",
            filetypes=[("ZIP", "*.zip"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            self.import_btn.configure(state="disabled")
        except Exception:
            pass

        def run():
            ok = False
            err = ""
            name = ""
            try:
                def progress(msg, pct=0):
                    self._set_progress(str(msg), float(pct) if pct is not None else 0)

                importer = ModpackImporter(self.settings)
                result = importer.import_pack(Path(path), progress_cb=progress)
                if isinstance(result, tuple) and len(result) >= 2:
                    ok = bool(result[0])
                    name = result[1] if len(result) > 1 else ""
                    err = result[2] if len(result) > 2 else ""
                else:
                    ok = bool(result)
            except Exception as e:
                logger.exception("import_pack failed")
                err = str(e)
            finally:
                def finish():
                    try:
                        if self.winfo_exists():
                            self.import_btn.configure(state="normal")
                            self.progress_bar.set(0)
                            self.progress_label.configure(text="")
                        if hasattr(self.main_window, "clear_status"):
                            self.main_window.clear_status()
                    except Exception:
                        pass
                    parent = self.main_window
                    if ok:
                        show_info(parent, "完成", f"模組包「{name}」導入成功！\n請到首頁啟動。")
                        try:
                            self.main_window.show_home()
                        except Exception:
                            pass
                    else:
                        show_error(parent, "導入失敗", err or "未知錯誤")
                self._ui(finish)

        threading.Thread(target=run, daemon=True).start()