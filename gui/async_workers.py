from PySide6.QtCore import QThread, Signal

from core.data_parser import CalorimetryParser
from core.kinetics_solver import KDSolver
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
            self.progress.emit("正在加载量热数据...")

            parser = CalorimetryParser(sample_mass_g=self.mass)
            data = parser.parse(self.filepath)
            self.data_loaded.emit(data)

            self.progress.emit("正在执行 K-D 动力学多峰联合解析...")

            solver = KDSolver(data, self.expected_peaks)
            params = solver.execute_pipeline()

            self.finished.emit((params, data))

        except Exception as e:
            logger.error(f"Worker 线程执行管线崩溃: {str(e)}")
            self.error.emit(str(e))
