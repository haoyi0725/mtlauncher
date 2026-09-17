# gui/download_page.py
# -*- coding: utf-8 -*-
import customtkinter as ctk
# 預留頁面，目前下載進度已整合在 versions_page 與 modpack_page
class DownloadPage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color="#07111F")
        ctk.CTkLabel(self, text="下載進度會顯示在建立/導入過程中", text_color="#94A3B8").pack(pady=40)