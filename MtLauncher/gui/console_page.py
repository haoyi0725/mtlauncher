import customtkinter as ctk
from core.logger import get_logs
class ConsolePage(ctk.CTkFrame):
    def __init__(self,master):
        super().__init__(master,fg_color="transparent")
        ctk.CTkLabel(self,text="遊戲日誌",font=ctk.CTkFont(size=28,weight="bold")).pack(anchor="w",padx=35,pady=(35,15))
        box=ctk.CTkTextbox(self,fg_color="#050C15",text_color="#B9C7D8",font=("Consolas",12))
        box.pack(fill="both",expand=True,padx=35,pady=(0,25))
        box.insert("end",get_logs() or "[MtLauncher] 目前沒有日誌。")
        box.configure(state="disabled")
