# -*- coding: utf-8 -*-
import customtkinter as ctk
import threading
from pathlib import Path
from core.version_manager import VersionManager
from core.fabric import FabricInstaller
from core.forge import ForgeInstaller
from core.neoforge import NeoForgeInstaller
from core.minecraft import MinecraftInstaller
from core.paths import get_versions_dir, get_minecraft_dir
from core.logger import get_logger
from gui.dialogs import show_info, show_error
import json
import re

logger = get_logger()

COLORS = {
    "bg": "#07111F",
    "card": "#0D1D31",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
    "dropdown": "#0D1D31",
    "hover": "#1E3A5F",
}

INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')

TYPE_MAP = {
    "正式版": ["release"],
    "快照版": ["snapshot"],
    "遠古版": ["ancient"],
    "愚人節版": ["april_fools"],
    "全部": None,
}

def safe_folder_name(name: str) -> str:
    name = name.strip()
    name = INVALID_CHARS.sub("_", name)
    return name.rstrip(". ")

class ScrollCombo(ctk.CTkFrame):
    def __init__(self, master, values=None, width=200, dropdown_height=200, command=None, **kwargs):
        super().__init__(master, fg_color="transparent")
        self._values = list(values or [])
        self._command = command
        self._dropdown_height = dropdown_height
        self._popup = None
        self._current = self._values[0] if self._values else ""

        self.entry = ctk.CTkEntry(self, width=width, height=32)
        self.entry.pack(side="left", fill="x", expand=True)
        if self._current:
            self.entry.insert(0, self._current)

        self.btn = ctk.CTkButton(
            self, text="▼", width=32, height=32,
            fg_color=COLORS["hover"], hover_color=COLORS["accent"],
            command=self._toggle
        )
        self.btn.pack(side="left", padx=(4, 0))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str):
        self._current = value or ""
        self.entry.delete(0, "end")
        self.entry.insert(0, self._current)

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._values = list(kwargs.pop("values") or [])
            if self._values and not self.get():
                self.set(self._values[0])
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            try:
                super().configure(**kwargs)
            except Exception:
                pass

    def _toggle(self):
        if self._popup and self._popup.winfo_exists():
            self._close()
        else:
            self._open()

    def _close(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

    def _open(self):
        self._close()
        if not self._values:
            return
        pop = ctk.CTkToplevel(self)
        pop.withdraw()
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        self._popup = pop

        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = max(self.winfo_width(), 220)
        h = self._dropdown_height
        pop.geometry(f"{w}x{h}+{x}+{y}")

        frame = ctk.CTkScrollableFrame(
            pop, fg_color=COLORS["dropdown"], width=w - 8, height=h - 8
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        for val in self._values:
            ctk.CTkButton(
                frame, text=val, anchor="w",
                fg_color="transparent", hover_color=COLORS["hover"],
                text_color=COLORS["text"], height=28,
                command=lambda v=val: self._select(v)
            ).pack(fill="x", padx=2, pady=1)

        pop.deiconify()
        pop.focus_force()
        pop.bind("<FocusOut>", lambda e: self.after(150, self._on_focus_out))
        pop.bind("<Escape>", lambda e: self._close())

    def _on_focus_out(self):
        if self._popup is None:
            return
        try:
            if self._popup.focus_get() is None:
                self._close()
        except Exception:
            self._close()

    def _select(self, value: str):
        self.set(value)
        self._close()
        if self._command:
            try:
                self._command(value)
            except Exception:
                pass

class VersionsPage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.settings = settings
        self.main_window = main_window
        self.vm = VersionManager()
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self, text="建立新實例",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        form = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        form.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="實例名稱", text_color=COLORS["text"]).grid(
            row=0, column=0, sticky="w", padx=15, pady=10
        )
        self.name_entry = ctk.CTkEntry(form, placeholder_text="例如：1.21.生存（可用 . ）")
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=15, pady=10)

        ctk.CTkLabel(form, text="版本類型", text_color=COLORS["text"]).grid(
            row=1, column=0, sticky="w", padx=15, pady=10
        )
        self.type_combo = ScrollCombo(
            form,
            values=["正式版", "快照版", "遠古版", "愚人節版", "全部"],
            dropdown_height=160,
            command=self.on_type_change
        )
        self.type_combo.grid(row=1, column=1, sticky="ew", padx=15, pady=10)
        self.type_combo.set("正式版")

        ctk.CTkLabel(form, text="Minecraft 版本", text_color=COLORS["text"]).grid(
            row=2, column=0, sticky="w", padx=15, pady=10
        )
        self.mc_combo = ScrollCombo(
            form, values=["載入中..."], dropdown_height=220, command=self.on_mc_change
        )
        self.mc_combo.grid(row=2, column=1, sticky="ew", padx=15, pady=10)

        ctk.CTkLabel(form, text="模組載入器", text_color=COLORS["text"]).grid(
            row=3, column=0, sticky="w", padx=15, pady=10
        )
        self.loader_combo = ScrollCombo(
            form, values=["Vanilla", "Fabric", "Forge", "NeoForge"],
            dropdown_height=140, command=self.on_loader_change
        )
        self.loader_combo.grid(row=3, column=1, sticky="ew", padx=15, pady=10)
        self.loader_combo.set("Vanilla")

        ctk.CTkLabel(form, text="Loader 版本", text_color=COLORS["text"]).grid(
            row=4, column=0, sticky="w", padx=15, pady=10
        )
        self.loader_ver_combo = ScrollCombo(
            form, values=["（原版無需選擇）"], dropdown_height=200
        )
        self.loader_ver_combo.grid(row=4, column=1, sticky="ew", padx=15, pady=10)

        self.progress_label = ctk.CTkLabel(form, text="", text_color=COLORS["text_dim"])
        self.progress_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        self.progress_bar = ctk.CTkProgressBar(form)
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        self.progress_bar.set(0)

        self.create_btn = ctk.CTkButton(
            form, text="建立並安裝", fg_color=COLORS["accent"], height=40,
            command=self.create_instance
        )
        self.create_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=15, pady=15)

        ctk.CTkLabel(
            form,
            text="遠古版 / 部分愚人節建議用 Vanilla\n路徑：data/.minecraft/versions/<名稱>/",
            text_color=COLORS["text_dim"], font=ctk.CTkFont(size=11), justify="left"
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 10))

        threading.Thread(target=self.load_versions, daemon=True).start()

    def load_versions(self):
        try:
            self.vm.fetch_manifest()
        except Exception as e:
            logger.error(f"fetch_manifest failed: {e}")
        self.after(0, self._reload_mc_list)

    def on_type_change(self, choice):
        self._reload_mc_list()

    def on_mc_change(self, choice):
        if not choice or choice.startswith("---") or choice.startswith("（"):
            return
        self.on_loader_change(self.loader_combo.get())

    def on_loader_change(self, choice):
        mc = self.mc_combo.get()
        if not mc or mc.startswith("---") or mc.startswith("（"):
            return
        if choice == "Vanilla":
            self.loader_ver_combo.configure(values=["（原版無需選擇）"])
            self.loader_ver_combo.set("（原版無需選擇）")
        elif choice == "Fabric":
            def fetch():
                try:
                    vers = FabricInstaller.get_loader_versions(mc)
                    vals = [v["version"] for v in vers] or ["無可用版本"]
                except Exception:
                    vals = ["無可用版本"]
                self.after(0, lambda: (
                    self.loader_ver_combo.configure(values=vals),
                    self.loader_ver_combo.set(vals[0] if vals else "")
                ))
            threading.Thread(target=fetch, daemon=True).start()
        elif choice == "Forge":
            def fetch():
                try:
                    vers = ForgeInstaller.get_forge_versions(mc) or ["無可用版本"]
                except Exception:
                    vers = ["無可用版本"]
                self.after(0, lambda: (
                    self.loader_ver_combo.configure(values=vers),
                    self.loader_ver_combo.set(vers[0] if vers else "")
                ))
            threading.Thread(target=fetch, daemon=True).start()
        elif choice == "NeoForge":
            def fetch():
                try:
                    vers = NeoForgeInstaller.get_neoforge_versions(mc) or ["無可用版本"]
                except Exception:
                    vers = ["無可用版本"]
                self.after(0, lambda: (
                    self.loader_ver_combo.configure(values=vers),
                    self.loader_ver_combo.set(vers[0] if vers else "")
                ))
            threading.Thread(target=fetch, daemon=True).start()

    def _reload_mc_list(self):
        choice = self.type_combo.get() if hasattr(self, "type_combo") else "正式版"
        types = TYPE_MAP.get(choice)

        try:
            if types is None:
                versions = self.vm.get_versions(None)
            else:
                versions = self.vm.get_versions(types)

            if choice == "快照版":
                versions = [v for v in versions if self.vm.classify(v) == "snapshot"]
            elif choice == "愚人節版":
                versions = [v for v in versions if self.vm.classify(v) == "april_fools"]
            elif choice == "遠古版":
                versions = [v for v in versions if self.vm.classify(v) == "ancient"]
            elif choice == "正式版":
                versions = [v for v in versions if self.vm.classify(v) == "release"]
        except Exception as e:
            logger.error(f"_reload_mc_list failed: {e}")
            versions = []

        ids = [v["id"] for v in versions]
        if choice == "正式版":
            ids = ids[:100]
        elif choice == "快照版":
            ids = ids[:80]
        elif choice == "遠古版":
            ids = ids[:120]
        elif choice == "愚人節版":
            ids = ids[:50]
        else:
            ids = ids[:150]

        if not ids:
            ids = ["（此分類無版本）"]

        self.mc_combo.configure(values=ids)
        self.mc_combo.set(ids[0])
        if not ids[0].startswith("（"):
            self.on_loader_change(self.loader_combo.get())

    def _rename_version_folder(self, official_id: str, user_name: str) -> str:
        versions_dir = get_versions_dir(self.settings)
        src = versions_dir / official_id
        dst = versions_dir / user_name
        if not src.exists():
            logger.warning(f"Official folder not found: {official_id}")
            return official_id
        if official_id == user_name:
            return official_id
        if dst.exists():
            logger.warning(f"Target exists, keep: {official_id}")
            return official_id
        try:
            src.rename(dst)
            logger.info(f"Renamed folder: {official_id} → {user_name}")
            return user_name
        except Exception as e:
            logger.error(f"Rename failed: {e}")
            return official_id

    def create_instance(self):
        raw_name = self.name_entry.get().strip()
        if not raw_name:
            show_error(self, "錯誤", "請輸入實例名稱")
            return
        if INVALID_CHARS.search(raw_name):
            show_error(self, "錯誤", "名稱不可包含：\\ / : * ? \" < > |")
            return
        safe = safe_folder_name(raw_name)
        if not safe:
            show_error(self, "錯誤", "實例名稱無效")
            return

        mc_ver = self.mc_combo.get()
        if not mc_ver or mc_ver.startswith("---") or mc_ver.startswith("（"):
            show_error(self, "錯誤", "請選擇有效的 Minecraft 版本")
            return

        loader = self.loader_combo.get().lower()
        loader_ver = self.loader_ver_combo.get()
        if loader != "vanilla" and (not loader_ver or "無可用" in loader_ver or "無需" in loader_ver):
            show_error(self, "錯誤", "請選擇有效的 Loader 版本（遠古/愚人節建議用 Vanilla）")
            return

        versions_dir = get_versions_dir(self.settings)
        if (versions_dir / safe).exists():
            show_error(self, "錯誤", f"實例「{safe}」已存在")
            return

        self.create_btn.configure(state="disabled")

        def run():
            success = False
            error_msg = ""
            final_id = safe
            try:
                def progress(msg, pct=0):
                    def update():
                        self._update_progress(msg, pct)
                        if hasattr(self.main_window, "set_status"):
                            self.main_window.set_status(msg, pct)
                    self.after(0, update)

                mc_root = get_minecraft_dir(self.settings)

                if loader == "fabric":
                    ok, official_id = FabricInstaller(mc_root, mc_ver, loader_ver, display_name=safe).install(progress)
                elif loader == "forge":
                    ok, official_id = ForgeInstaller(mc_root, mc_ver, loader_ver, display_name=safe).install(progress)
                elif loader == "neoforge":
                    ok, official_id = NeoForgeInstaller(mc_root, mc_ver, loader_ver, display_name=safe).install(progress)
                else:
                    ok, official_id = MinecraftInstaller(mc_root, mc_ver, display_name=safe).install(progress)

                if ok and official_id:
                    final_id = self._rename_version_folder(official_id, safe)
                    vdir = versions_dir / final_id
                    vdir.mkdir(parents=True, exist_ok=True)
                    (vdir / "mods").mkdir(exist_ok=True)
                    meta = {
                        "name": safe,
                        "mc_version": mc_ver,
                        "loader": loader,
                        "loader_version": loader_ver if loader != "vanilla" else "",
                        "version_id": final_id,
                        "official_id": official_id
                    }
                    with open(vdir / "mt_instance.json", "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
                    success = True
                else:
                    error_msg = "安裝失敗，請查看日誌"
            except Exception as e:
                logger.exception("Create instance failed")
                error_msg = str(e)
            finally:
                def finish():
                    try:
                        if self.winfo_exists():
                            self.create_btn.configure(state="normal")
                            self.progress_bar.set(0)
                            self.progress_label.configure(text="")
                        if hasattr(self.main_window, "clear_status"):
                            self.main_window.clear_status()
                    except Exception:
                        pass
                    if success:
                        show_info(
                            self, "完成",
                            f"實例「{safe}」建立成功！\n\ndata/.minecraft/versions/{final_id}/"
                        )
                        self.main_window.show_home()
                    elif error_msg:
                        show_error(self, "錯誤", error_msg)
                self.after(0, finish)

        threading.Thread(target=run, daemon=True).start()

    def _update_progress(self, msg: str, pct: float):
        try:
            if self.winfo_exists():
                self.progress_label.configure(text=msg)
                self.progress_bar.set(max(0.0, min(1.0, pct)))
        except Exception:
            pass