import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from gui.main_window import MainWindow
from utils.logger import logger

def get_asset_path(filename: str) -> str:
    """极其关键：兼容单文件打包的临时解压路径"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 单文件打包运行时的 C 盘临时目录
        base_path = Path(sys._MEIPASS) / "assets"
    else:
        # 开发时的相对目录
        base_path = Path(__file__).resolve().parent / "assets"
    return str(base_path / filename)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon(get_asset_path("lq.ico")))
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Application crashed: {str(e)}")