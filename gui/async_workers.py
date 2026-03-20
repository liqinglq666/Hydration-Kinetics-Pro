from PySide6.QtCore import QThread, Signal
from core.data_models import HydrationData
from core.kinetics_solver import KDSolver
from core.data_parser import CalorimetryParser
from utils.logger import logger


class KineticsWorker(QThread):
    progress = Signal(str)
    data_loaded = Signal(object)
    finished = Signal(tuple)
    error = Signal(str)

    def __init__(self, filepath, mass, expected_peaks):
        super().__init__()
        self.filepath = filepath
        self.mass = float(mass)
        self.expected_peaks = expected_peaks

    def run(self):
        try:
            self.progress.emit("正在通过核心解析引擎加载数据...")

            # 架构重构：将底层 I/O、格式路由(CSV/Excel)与数据清洗彻底委托给专用解析器
            # 严格遵守职责分离原则，Worker 线程仅负责管线调度
            parser = CalorimetryParser(sample_mass_g=self.mass)
            data = parser.parse(self.filepath)

            # 将纯净数据发送给 UI 进行初步预览
            self.data_loaded.emit(data)

            self.progress.emit("正在执行 K-D 动力学多峰联合解析...")

            # 调起核心解算器
            solver = KDSolver(data, self.expected_peaks)
            params = solver.execute_pipeline()

            self.finished.emit((params, data))

        except Exception as e:
            logger.error(f"Worker 线程执行管线崩溃: {str(e)}")
            self.error.emit(str(e))