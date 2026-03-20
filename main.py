import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from utils.logger import logger


def main() -> None:
    app = QApplication(sys.argv)

    # FIXME: 移除了弃用的 Qt.AA_EnableHighDpiScaling 和 Qt.AA_UseHighDpiPixmaps
    # PySide6 默认已在底层引擎层面全局开启高 DPI 支持，无需显式声明

    window = MainWindow()
    window.show()
    logger.info("HydrationKineticsPro GUI 环境初始化完毕。")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()