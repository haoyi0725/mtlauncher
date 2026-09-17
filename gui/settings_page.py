# -*- coding: utf-8 -*-
import customtkinter as ctk
import platform
import subprocess
from pathlib import Path
from tkinter import filedialog
from gui.dialogs import show_info, show_error, ask_yes_no
from core.skin import (
    save_skin,
    get_player_skin,
    remove_player_skin,
    get_resource_pack_path,
)

COLORS = {
    "bg": "#07111F",
    "card": "#0D1D31",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
    "hover": "#1E3A5F",
}

class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.settings = settings
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="設定",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        form = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        form.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        form.grid_columnconfigure(1, weight=1)

        # 玩家名稱
        ctk.CTkLabel(form, text="玩家名稱", text_color=COLORS["text"]).grid(
            row=0, column=0, sticky="w", padx=15, pady=12
        )
        self.name_entry = ctk.CTkEntry(form, width=280)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=15, pady=12)
        current_name = self.settings.get("player_name") or "Steve"
        self.name_entry.insert(0, str(current_name))

        # 記憶體
        ctk.CTkLabel(form, text="最小記憶體 (MB)", text_color=COLORS["text"]).grid(
            row=1, column=0, sticky="w", padx=15, pady=12
        )
        self.min_ram = ctk.CTkEntry(form, width=120)
        self.min_ram.grid(row=1, column=1, sticky="w", padx=15, pady=12)
        self.min_ram.insert(0, str(self.settings.get("min_ram", 2048)))

        ctk.CTkLabel(form, text="最大記憶體 (MB)", text_color=COLORS["text"]).grid(
            row=2, column=0, sticky="w", padx=15, pady=12
        )
        self.max_ram = ctk.CTkEntry(form, width=120)
        self.max_ram.grid(row=2, column=1, sticky="w", padx=15, pady=12)
        self.max_ram.insert(0, str(self.settings.get("max_ram", 4096)))

        # Java
        ctk.CTkLabel(form, text="Java 路徑（可留空自動選擇）", text_color=COLORS["text"]).grid(
            row=3, column=0, sticky="w", padx=15, pady=12
        )
        java_row = ctk.CTkFrame(form, fg_color="transparent")
        java_row.grid(row=3, column=1, sticky="ew", padx=15, pady=12)
        java_row.grid_columnconfigure(0, weight=1)
        self.java_entry = ctk.CTkEntry(java_row)
        self.java_entry.grid(row=0, column=0, sticky="ew")
        self.java_entry.insert(0, str(self.settings.get("java_path", "") or ""))
        ctk.CTkButton(
            java_row, text="瀏覽", width=70,
            fg_color=COLORS["hover"], command=self.browse_java
        ).grid(row=0, column=1, padx=(8, 0))

        # JVM / 遊戲參數
        ctk.CTkLabel(form, text="額外 JVM 參數", text_color=COLORS["text"]).grid(
            row=4, column=0, sticky="w", padx=15, pady=12
        )
        self.jvm_entry = ctk.CTkEntry(form)
        self.jvm_entry.grid(row=4, column=1, sticky="ew", padx=15, pady=12)
        self.jvm_entry.insert(0, str(self.settings.get("jvm_args", "") or ""))

        ctk.CTkLabel(form, text="額外遊戲參數", text_color=COLORS["text"]).grid(
            row=5, column=0, sticky="w", padx=15, pady=12
        )
        self.mc_entry = ctk.CTkEntry(form)
        self.mc_entry.grid(row=5, column=1, sticky="ew", padx=15, pady=12)
        self.mc_entry.insert(0, str(self.settings.get("mc_args", "") or ""))

        # 皮膚
        ctk.CTkLabel(form, text="自訂皮膚 (PNG)", text_color=COLORS["text"]).grid(
            row=6, column=0, sticky="w", padx=15, pady=12
        )
        skin_row = ctk.CTkFrame(form, fg_color="transparent")
        skin_row.grid(row=6, column=1, sticky="ew", padx=15, pady=12)

        self.skin_label = ctk.CTkLabel(
            skin_row, text="未選擇", text_color=COLORS["text_dim"], anchor="w"
        )
        self.skin_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            skin_row, text="清除", width=70,
            fg_color="#7F1D1D", hover_color="#991B1B",
            command=self.clear_skin
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            skin_row, text="上傳 PNG", width=100,
            fg_color=COLORS["hover"], command=self.upload_skin
        ).pack(side="right", padx=4)

        sk = get_player_skin(self.settings.get_data_root(), str(current_name))
        if sk and sk.exists():
            self.skin_label.configure(text=sk.name, text_color=COLORS["text"])
        elif self.settings.get("custom_skin"):
            p = Path(str(self.settings.get("custom_skin")))
            if p.exists():
                self.skin_label.configure(text=p.name, text_color=COLORS["text"])

        ctk.CTkLabel(
            form,
            text="上傳後會產生資源包 MtLauncher_Skin.zip。\n"
                 "請儲存設定，並在遊戲「選項 → 資源包」中啟用（不是資料包）。",
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=11),
            justify="left"
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        # 儲存
        ctk.CTkButton(
            form, text="儲存設定", height=40, fg_color=COLORS["accent"],
            command=self.save_settings
        ).grid(row=8, column=0, columnspan=2, sticky="ew", padx=15, pady=20)

        ctk.CTkLabel(
            form,
            text=f"設定檔：{self.settings.get_data_root() / 'settings.json'}",
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=11)
        ).grid(row=9, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 12))

    def browse_java(self):
        path = filedialog.askopenfilename(
            title="選擇 java.exe",
            filetypes=[("java", "java.exe"), ("All", "*.*")]
        )
        if path:
            self.java_entry.delete(0, "end")
            self.java_entry.insert(0, path)

    def _open_folder(self, folder: Path):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        path = str(folder.resolve())
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            show_error(self.main_window, "錯誤", f"無法開啟資料夾：{e}")

    def upload_skin(self):
        path = filedialog.askopenfilename(
            title="選擇皮膚 PNG（建議 64×64）",
            filetypes=[("PNG 圖片", "*.png"), ("All", "*.*")]
        )
        if not path:
            return
        name = self.name_entry.get().strip() or self.settings.get("player_name", "Steve")
        try:
            result = save_skin(self.settings.get_data_root(), name, Path(path))
            if isinstance(result, tuple):
                skin_path, pack_path = result[0], result[1]
            else:
                skin_path = result
                pack_path = get_resource_pack_path(self.settings.get_data_root())

            skin_path = Path(skin_path)
            pack_path = Path(pack_path)

            self.settings.set("custom_skin", str(skin_path))
            self.skin_label.configure(
                text=skin_path.name,
                text_color=COLORS["text"]
            )

            show_info(
                self.main_window,
                "完成",
                "已建立資源包！\n\n"
                f"{pack_path}\n\n"
                "請記得：\n"
                "1. 按「儲存設定」\n"
                "2. 放到 Minecraft「資源包」並啟用（選項 → 資源包，不是資料包）\n"
                "（啟動器啟動時也會嘗試自動放進實例 resourcepacks）"
            )

            if ask_yes_no(self.main_window, "打開資料夾", "要打開資源包所在資料夾嗎？"):
                self._open_folder(pack_path.parent)
        except Exception as e:
            show_error(self.main_window, "錯誤", str(e))

    def clear_skin(self):
        name = self.name_entry.get().strip() or self.settings.get("player_name", "Steve")
        try:
            remove_player_skin(self.settings.get_data_root(), name)
        except Exception:
            pass
        self.settings.set("custom_skin", "")
        self.skin_label.configure(text="未選擇", text_color=COLORS["text_dim"])
        show_info(self.main_window, "完成", "已清除自訂皮膚")

    def save_settings(self):
        name = self.name_entry.get().strip()
        if not name:
            show_error(self.main_window, "錯誤", "玩家名稱不能為空")
            return
        try:
            min_ram = int(self.min_ram.get().strip())
            max_ram = int(self.max_ram.get().strip())
        except ValueError:
            show_error(self.main_window, "錯誤", "記憶體必須是數字")
            return
        if min_ram < 512 or max_ram < min_ram:
            show_error(
                self.main_window, "錯誤",
                "記憶體設定不合理（最大需 ≥ 最小，最小 ≥ 512）"
            )
            return

        self.settings.set("player_name", name)
        self.settings.set("min_ram", min_ram)
        self.settings.set("max_ram", max_ram)
        self.settings.set("java_path", self.java_entry.get().strip())
        self.settings.set("jvm_args", self.jvm_entry.get().strip())
        self.settings.set("mc_args", self.mc_entry.get().strip())

        sk = get_player_skin(self.settings.get_data_root(), name)
        if sk and sk.exists():
            self.settings.set("custom_skin", str(sk))
            self.skin_label.configure(text=sk.name, text_color=COLORS["text"])

        self.settings.save()

        path = self.settings.get_data_root() / "settings.json"
        show_info(
            self.main_window, "已儲存",
            f"玩家名稱：{name}\n\n已寫入：\n{path}"
        )