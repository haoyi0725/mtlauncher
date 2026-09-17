# gui/instance_page.py
# -*- coding: utf-8 -*-
import customtkinter as ctk
# 預留，詳細實例管理可擴充
class InstancePage(ctk.CTkFrame):
    def __init__(self, parent, settings, main_window):
        super().__init__(parent, fg_color="#07111F")