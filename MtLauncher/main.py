# -*- coding: utf-8 -*-
"""
MtLauncher 入口
"""
import sys
import traceback
from core.app_paths import ensure_runtime_dirs
ensure_runtime_dirs()

# Windows：工作列使用獨立 AppID（避免一直顯示 Python 圖示）
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xAI.MtLauncher.1.0")
    except Exception:
        pass

def main():
    try:
        from core.app_paths import ensure_runtime_dirs
        ensure_runtime_dirs()

        from core.settings import Settings
        from core.logger import setup_logger, get_logger
        from gui.main_window import MainWindow

        settings = Settings()
        setup_logger()
        logger = get_logger()
        logger.info("MtLauncher starting...")

        app = MainWindow(settings)
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            print("FATAL ERROR:\n", err)
        except Exception:
            pass
        # 打包成 windowed 時沒有主控台，寫入檔案方便除錯
        try:
            from core.app_paths import get_app_dir
            crash = get_app_dir() / "crash.txt"
            crash.write_text(err, encoding="utf-8")
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()