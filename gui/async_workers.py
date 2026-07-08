from PySide6.QtCore import QThread, Signal

from core.data_parser import CalorimetryParser
from core.kinetics_solver import KDSolver
from utils.logger import logger


class KineticsWorker(QThread):
    progress = Signal(str)
    data_loaded = Signal(object)
    analysis_finished = Signal(tuple)
    error = Signal(str)

    def __init__(
        self,
        filepath,
        mass,
        expected_peaks,
        input_mode,
        use_manual_t0=False,
        manual_t0_h=0.0,
        use_manual_qmax=False,
        manual_qmax_total_j_g=0.0,
        allow_qmax_fallback=True,
    ):
        super().__init__()
        self.filepath = filepath
        self.mass = float(mass)
        self.expected_peaks = int(expected_peaks)
        self.input_mode = str(input_mode)
        self.manual_t0_h = float(manual_t0_h) if use_manual_t0 else None
        self.manual_qmax_total_j_g = float(manual_qmax_total_j_g) if use_manual_qmax else None
        self.allow_qmax_fallback = bool(allow_qmax_fallback)

    def run(self):
        try:
            self.progress.emit("正在加载量热数据...")

            parser = CalorimetryParser(sample_mass_g=self.mass, input_mode=self.input_mode)
            data = parser.parse(self.filepath)
            self.data_loaded.emit(data)

            self.progress.emit("正在执行 K-D 动力学多峰联合解析...")

            solver = KDSolver(
                data,
                self.expected_peaks,
                manual_t0_h=self.manual_t0_h,
                manual_qmax_total_j_g=self.manual_qmax_total_j_g,
                allow_qmax_fallback=self.allow_qmax_fallback,
            )
            params = solver.execute_pipeline()

            self.analysis_finished.emit((params, data))

        except Exception as e:
            logger.error(f"Worker 线程执行管线崩溃: {str(e)}")
            self.error.emit(str(e))
