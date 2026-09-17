# -*- coding: utf-8 -*-
import customtkinter as ctk
from core import game_log
from core.logger import get_logger

logger = get_logger()

COLORS = {
    "bg": "#07111F",
    "card": "#0D1D31",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
}

class LogsPage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.settings = settings
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._auto_scroll = True
        self._poll_job = None

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            top, text="遊戲日誌",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        ctk.CTkButton(
            top, text="清空", width=80, height=30,
            fg_color="#1E3A5F", hover_color="#122A46",
            command=self.clear_logs
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            top, text="複製全部", width=90, height=30,
            fg_color="#1E3A5F", hover_color="#122A46",
            command=self.copy_all
        ).pack(side="right", padx=4)

        self.textbox = ctk.CTkTextbox(
            self, fg_color=COLORS["card"], text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="char"
        )
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.textbox.configure(state="normal")
        self.textbox.insert("1.0", "（尚無日誌。請到首頁啟動遊戲，日誌會即時顯示在這裡。）\n")
        self.textbox.configure(state="disabled")

        # 載入已有緩衝
        self._reload_from_buffer()
        # 訂閱新行
        game_log.subscribe(self._on_new_line)
        # 定時保險刷新
        self._poll_job = self.after(500, self._poll)

        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event=None):
        if event and event.widget is not self:
            return
        try:
            game_log.unsubscribe(self._on_new_line)
        except Exception:
            pass
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass

    def _reload_from_buffer(self):
        lines = game_log.get_all()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        if not lines:
            self.textbox.insert("1.0", "（尚無日誌。請到首頁啟動遊戲，日誌會即時顯示在這裡。）\n")
        else:
            self.textbox.insert("1.0", "\n".join(lines) + "\n")
        self.textbox.configure(state="disabled")
        if self._auto_scroll:
            self.textbox.see("end")

    def _on_new_line(self, line: str):
        # 可能在背景執行緒呼叫 → 轉主執行緒
        try:
            self.after(0, lambda l=line: self._append_line(l))
        except Exception:
            pass

    def _append_line(self, line: str):
        try:
            if not self.winfo_exists():
                return
            self.textbox.configure(state="normal")
            # 若還是提示文字，先清掉
            content = self.textbox.get("1.0", "end").strip()
            if content.startswith("（尚無日誌"):
                self.textbox.delete("1.0", "end")
            self.textbox.insert("end", line + "\n")
            self.textbox.configure(state="disabled")
            if self._auto_scroll:
                self.textbox.see("end")
        except Exception:
            pass

    def _poll(self):
        # 備用：防止訂閱漏接
        try:
            if self.winfo_exists():
                self._poll_job = self.after(800, self._poll)
        except Exception:
            pass

    def clear_logs(self):
        game_log.clear()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", "（日誌已清空）\n")
        self.textbox.configure(state="disabled")

    def copy_all(self):
        try:
            text = self.textbox.get("1.0", "end")
            self.clipboard_clear()
            self.clipboard_append(text)
            show_tip = getattr(self.main_window, "set_status", None)
            if show_tip:
                self.main_window.set_status("日誌已複製到剪貼簿", 1.0)
                self.after(1500, lambda: self.main_window.clear_status())
        except Exception:
            pass