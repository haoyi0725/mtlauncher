# -*- coding: utf-8 -*-
import customtkinter as ctk
from pathlib import Path
import json
import threading
import shutil
import zipfile
import subprocess
import platform
import tempfile
import re
from tkinter import filedialog
from gui.dialogs import show_info, show_error, ask_yes_no, ask_string
from core.launcher import Launcher
from core.paths import get_versions_dir
from core.logger import get_logger
from core import game_log

logger = get_logger()

COLORS = {
    "bg": "#07111F",
    "card": "#0D1D31",
    "hover": "#122A46",
    "accent": "#3B82F6",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
}

INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.settings = settings
        self.main_window = main_window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._menu_popup = None
        self._outside_bind_id = None

        title = ctk.CTkLabel(
            self, text="我的實例",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"])
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.scroll.grid_columnconfigure(0, weight=1)
        self.refresh()

    def _list_instances(self):
        versions_dir = get_versions_dir(self.settings)
        result = []
        if not versions_dir.exists():
            return result
        for d in sorted(versions_dir.iterdir(), key=lambda p: p.name.lower()):
            if not d.is_dir():
                continue
            jsons = [j for j in d.glob("*.json") if j.name != "mt_instance.json"]
            if not jsons:
                continue
            info = {
                "name": d.name,
                "version_id": d.name,
                "mc_version": "?",
                "loader": "vanilla",
                "loader_version": "",
                "path": d,
            }
            meta = d / "mt_instance.json"
            if meta.exists():
                try:
                    with open(meta, "r", encoding="utf-8") as f:
                        info.update(json.load(f))
                except Exception:
                    pass
            info["version_id"] = d.name
            info["path"] = d
            result.append(info)
        return result

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        instances = self._list_instances()
        if not instances:
            ctk.CTkLabel(
                self.scroll,
                text="尚無實例，請到「建立版本」建立\n路徑：data/.minecraft/versions/",
                text_color=COLORS["text_dim"],
                font=ctk.CTkFont(size=14)
            ).pack(pady=40)
            return
        for info in instances:
            self._add_card(info)

    def _add_card(self, info: dict):
        card = ctk.CTkFrame(self.scroll, fg_color=COLORS["card"], corner_radius=10)
        card.pack(fill="x", pady=8, padx=5)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=15, pady=12)

        display_name = info.get("name") or info.get("version_id")
        ctk.CTkLabel(
            left, text=display_name,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w")

        desc = f"Minecraft {info.get('mc_version', '?')}"
        loader = (info.get("loader") or "vanilla").lower()
        if loader and loader != "vanilla":
            desc += f"  ·  {loader.capitalize()} {info.get('loader_version', '')}"
        else:
            desc += "  ·  Vanilla"
        ctk.CTkLabel(
            left, text=desc,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        ).pack(anchor="w", pady=(2, 0))

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(side="right", padx=10, pady=10)

        launch_btn = ctk.CTkButton(
            btn_frame, text="▶ 啟動", width=100, height=32,
            fg_color=COLORS["accent"], hover_color="#2563EB",
        )
        launch_btn.configure(command=lambda i=info, b=launch_btn: self.launch_instance(i, b))
        launch_btn.pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="📂", width=40, height=32,
            fg_color=COLORS["hover"], hover_color="#1E3A5F",
            command=lambda i=info: self.open_folder(Path(i["path"]))
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="⋮", width=40, height=32,
            fg_color=COLORS["hover"], hover_color="#1E3A5F",
            command=lambda i=info, b=btn_frame: self.show_menu(i, b)
        ).pack(side="left", padx=4)

    def show_menu(self, info: dict, anchor_widget):
        self._close_menu()
        pop = ctk.CTkToplevel(self)
        pop.withdraw()
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        self._menu_popup = pop

        frame = ctk.CTkFrame(
            pop, fg_color=COLORS["card"], corner_radius=8,
            border_width=1, border_color="#1E3A5F"
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        loader = (info.get("loader") or "vanilla").lower()

        def item(text, cmd, danger=False):
            def on_click():
                self._close_menu()
                self.after(10, cmd)
            ctk.CTkButton(
                frame, text=text, anchor="w", height=34,
                fg_color="transparent",
                hover_color="#7F1D1D" if danger else COLORS["hover"],
                text_color="#FCA5A5" if danger else COLORS["text"],
                command=on_click
            ).pack(fill="x", padx=6, pady=2)

        item("✏  更改名稱", lambda: self.rename_instance(info))
        item("📦  導出 CurseForge 模組包", lambda: self.export_curseforge(info))
        if loader != "vanilla":
            item("🧩  打開 Mods 資料夾", lambda: self.open_mods(info))
        item("🌍  打開世界資料夾", lambda: self.open_saves(info))
        item("📂  打開實例資料夾", lambda: self.open_folder(Path(info["path"])))
        item("🗑  刪除實例", lambda: self.delete_instance(info), danger=True)

        pop.update_idletasks()
        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx() - 160
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        w, h = 220, frame.winfo_reqheight() + 8
        if x < 0:
            x = anchor_widget.winfo_rootx()
        pop.geometry(f"{w}x{h}+{x}+{y}")
        pop.deiconify()
        pop.lift()
        pop.focus_force()

        def bind_outside_close():
            if self._menu_popup is None or not self._menu_popup.winfo_exists():
                return

            def on_root_click(event):
                if self._menu_popup is None:
                    return
                try:
                    px = self._menu_popup.winfo_rootx()
                    py = self._menu_popup.winfo_rooty()
                    pw = self._menu_popup.winfo_width()
                    ph = self._menu_popup.winfo_height()
                    if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                        return
                    self._close_menu()
                except Exception:
                    self._close_menu()

            self._outside_bind_id = self.winfo_toplevel().bind("<Button-1>", on_root_click, add="+")
            self._menu_popup.bind("<Escape>", lambda e: self._close_menu())

        self.after(250, bind_outside_close)

    def _close_menu(self):
        if self._outside_bind_id:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._outside_bind_id)
            except Exception:
                try:
                    self.winfo_toplevel().unbind("<Button-1>")
                except Exception:
                    pass
            self._outside_bind_id = None
        if self._menu_popup is not None:
            try:
                self._menu_popup.destroy()
            except Exception:
                pass
            self._menu_popup = None

    def launch_instance(self, info: dict, launch_btn=None):
        def set_btn_launching():
            if launch_btn is None:
                return
            try:
                if launch_btn.winfo_exists():
                    launch_btn.configure(
                        text="啟動中…",
                        state="disabled",
                        fg_color="#475569",
                        hover_color="#475569"
                    )
            except Exception:
                pass

        def set_btn_idle():
            if launch_btn is None:
                return
            try:
                if launch_btn.winfo_exists():
                    launch_btn.configure(
                        text="▶ 啟動",
                        state="normal",
                        fg_color=COLORS["accent"],
                        hover_color="#2563EB"
                    )
            except Exception:
                pass

        set_btn_launching()
        display = info.get("name") or info.get("version_id")
        game_log.append(f"======== 啟動 {display} ========")

        def run():
            launcher = Launcher(self.settings)
            version_id = info.get("version_id") or info.get("name")

            def log_cb(msg):
                logger.info(msg)
                game_log.append(msg)

            try:
                ok = launcher.launch(version_id, log_callback=log_cb)
                game_log.append(f"======== 結束（成功={ok}）========")
                if not ok:
                    self.after(0, lambda: show_error(
                        self.main_window, "啟動失敗",
                        f"版本 {version_id} 啟動失敗，請查看「遊戲日誌」"
                    ))
            except Exception as e:
                logger.exception("launch failed")
                game_log.append(f"[錯誤] {e}")
                self.after(0, lambda err=str(e): show_error(self.main_window, "啟動失敗", err))
            finally:
                self.after(0, set_btn_idle)

        threading.Thread(target=run, daemon=True).start()

    def open_folder(self, path: Path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            show_error(self.main_window, "錯誤", f"無法開啟：{e}")

    def open_mods(self, info: dict):
        mods = Path(info["path"]) / "mods"
        mods.mkdir(parents=True, exist_ok=True)
        self.open_folder(mods)

    def open_saves(self, info: dict):
        saves = Path(info["path"]) / "saves"
        saves.mkdir(parents=True, exist_ok=True)
        self.open_folder(saves)

    def rename_instance(self, info: dict):
        old_id = info.get("version_id") or info.get("name")
        old_path = Path(info["path"])
        current_name = info.get("name") or old_id

        new_name = ask_string(
            self.main_window, "更改名稱",
            f"目前名稱：{current_name}\n\n請輸入新名稱：\n（只改資料夾名，不改 jar/json）",
            initial=current_name
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if INVALID_CHARS.search(new_name):
            show_error(self.main_window, "錯誤", "名稱不可包含：\\ / : * ? \" < > |")
            return
        new_name = new_name.rstrip(". ")
        if not new_name:
            show_error(self.main_window, "錯誤", "名稱無效")
            return
        if new_name == old_id:
            show_info(self.main_window, "提示", "名稱未變更")
            return

        versions_dir = get_versions_dir(self.settings)
        new_path = versions_dir / new_name
        if new_path.exists():
            show_error(self.main_window, "錯誤", f"「{new_name}」已存在")
            return

        try:
            old_path.rename(new_path)
            meta_path = new_path / "mt_instance.json"
            meta = {
                "name": new_name,
                "mc_version": info.get("mc_version", "?"),
                "loader": info.get("loader", "vanilla"),
                "loader_version": info.get("loader_version", ""),
                "version_id": new_name,
                "official_id": info.get("official_id") or info.get("mc_version") or old_id,
            }
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        old_meta = json.load(f)
                    if old_meta.get("official_id"):
                        meta["official_id"] = old_meta["official_id"]
                    old_meta.update(meta)
                    meta = old_meta
                except Exception:
                    pass
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            logger.info(f"Renamed folder: {old_id} → {new_name}")
            show_info(self.main_window, "完成", f"已更名為「{new_name}」")
            self.refresh()
        except Exception as e:
            logger.exception("Rename failed")
            show_error(self.main_window, "錯誤", f"更名失敗：{e}")

    def delete_instance(self, info: dict):
        name = info.get("name") or info.get("version_id")
        path = Path(info["path"])
        if not ask_yes_no(
            self.main_window, "確認刪除",
            f"確定刪除實例「{name}」？\n\n{path}\n\n無法復原！"
        ):
            return
        try:
            shutil.rmtree(path)
            logger.info(f"Deleted instance: {path}")
            show_info(self.main_window, "完成", f"已刪除「{name}」")
            self.refresh()
        except Exception as e:
            show_error(self.main_window, "錯誤", f"刪除失敗：{e}")

    def export_curseforge(self, info: dict):
        name = info.get("name") or info.get("version_id") or "pack"
        version_dir = Path(info["path"])
        mc_ver = info.get("mc_version") or "?"
        loader = (info.get("loader") or "vanilla").lower()
        loader_ver = info.get("loader_version") or ""

        out = filedialog.asksaveasfilename(
            title="導出 CurseForge 模組包",
            defaultextension=".zip",
            initialfile=f"{name}-curseforge.zip",
            filetypes=[("ZIP", "*.zip")]
        )
        if not out:
            return

        def run():
            try:
                mod_loaders = []
                if loader == "forge" and loader_ver:
                    fv = loader_ver
                    if fv.startswith(mc_ver + "-"):
                        fv = fv[len(mc_ver) + 1:]
                    mod_loaders = [{"id": f"forge-{fv}", "primary": True}]
                elif loader == "neoforge" and loader_ver:
                    mod_loaders = [{"id": f"neoforge-{loader_ver}", "primary": True}]
                elif loader == "fabric" and loader_ver:
                    mod_loaders = [{"id": f"fabric-{loader_ver}", "primary": True}]

                manifest = {
                    "minecraft": {"version": mc_ver, "modLoaders": mod_loaders},
                    "manifestType": "minecraftModpack",
                    "manifestVersion": 1,
                    "name": name,
                    "version": "1.0.0",
                    "author": "MtLauncher",
                    "files": [],
                    "overrides": "overrides"
                }
                mods_dir = version_dir / "mods"
                mod_names = [m.name for m in sorted(mods_dir.glob("*.jar"))] if mods_dir.exists() else []

                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    with open(tmp_path / "manifest.json", "w", encoding="utf-8") as f:
                        json.dump(manifest, f, ensure_ascii=False, indent=2)
                    with open(tmp_path / "modlist.html", "w", encoding="utf-8") as f:
                        f.write("<ul>\n" + "".join(f"<li>{n}</li>\n" for n in mod_names) + "</ul>\n")
                    overrides = tmp_path / "overrides"
                    overrides.mkdir()
                    for folder in ("mods", "config", "resourcepacks", "shaderpacks", "defaultconfigs"):
                        src = version_dir / folder
                        if src.exists():
                            shutil.copytree(src, overrides / folder, dirs_exist_ok=True)
                    for fname in ("options.txt", "optionsof.txt", "servers.dat"):
                        src = version_dir / fname
                        if src.exists():
                            shutil.copy2(src, overrides / fname)
                    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                        for p in tmp_path.rglob("*"):
                            if p.is_file():
                                zf.write(p, p.relative_to(tmp_path).as_posix())

                self.after(0, lambda: show_info(
                    self.main_window, "導出完成",
                    f"已導出：\n{out}\n\n模組：{len(mod_names)}"
                ))
            except Exception as e:
                logger.exception("Export failed")
                self.after(0, lambda: show_error(self.main_window, "導出失敗", str(e)))

        threading.Thread(target=run, daemon=True).start()
        show_info(self.main_window, "導出", "正在打包，請稍候…")