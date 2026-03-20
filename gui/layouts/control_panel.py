from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QDoubleSpinBox, QHBoxLayout, QLineEdit, \
    QSpinBox
from PySide6.QtCore import Signal


class ControlPanel(QWidget):
    load_requested = Signal()
    # NOTE: 信号新增传递 expected_peaks (int)
    calculate_requested = Signal(float, int)
    extract_requested = Signal(str)
    export_excel_requested = Signal()
    export_images_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # --- 基础控制区 ---
        self.btn_load = QPushButton("导入量热数据 (CSV)")
        self.btn_calc = QPushButton("执行动力学全解析")
        self.btn_calc.setEnabled(False)

        # 参数配置布局
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("有效质量 (g):"))
        self.spin_mass = QDoubleSpinBox()
        self.spin_mass.setRange(0.01, 1000.0)
        self.spin_mass.setValue(1.00)
        self.spin_mass.setSingleStep(0.1)
        param_layout.addWidget(self.spin_mass)

        # NOTE: 新增预期特征峰数量选择器
        param_layout.addSpacing(10)
        param_layout.addWidget(QLabel("预期特征峰数:"))
        self.spin_peaks = QSpinBox()
        self.spin_peaks.setRange(1, 4)  # 物理极限一般是 3，这里给 4 留有余地
        self.spin_peaks.setValue(1)  # 默认 1 个主峰
        param_layout.addWidget(self.spin_peaks)

        # --- 辅助工具区 ---
        extract_layout = QHBoxLayout()
        extract_layout.addWidget(QLabel("目标时间 (h):"))
        self.input_times = QLineEdit("1, 10, 24, 48, 60, 72")
        self.input_times.setPlaceholderText("如: 1, 24, 72")
        extract_layout.addWidget(self.input_times)

        self.btn_extract = QPushButton("提取特定龄期热量")
        self.btn_extract.setEnabled(False)

        # --- 导出模块 ---
        self.btn_export_excel = QPushButton("导出 Excel 数据报表")
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setStyleSheet(
            "background-color: #f8f9fa; font-weight: bold; border: 1px solid #ced4da; padding: 5px;")

        self.btn_export_images = QPushButton("保存四宫格科研图像")
        self.btn_export_images.setEnabled(False)
        self.btn_export_images.setStyleSheet(
            "background-color: #f8f9fa; font-weight: bold; border: 1px solid #ced4da; padding: 5px;")

        self.lbl_status = QLabel("状态: 等待载入")
        self.lbl_status.setStyleSheet("color: #6c757d; font-weight: bold;")

        # --- 布局组装 ---
        layout.addWidget(self.btn_load)
        layout.addLayout(param_layout)
        layout.addWidget(self.btn_calc)

        layout.addSpacing(15)
        layout.addWidget(QLabel("<b>工程辅助提取</b>"))
        layout.addLayout(extract_layout)
        layout.addWidget(self.btn_extract)

        layout.addSpacing(15)
        layout.addWidget(QLabel("<b>科研成果输出</b>"))
        layout.addWidget(self.btn_export_excel)
        layout.addWidget(self.btn_export_images)

        layout.addSpacing(15)
        layout.addWidget(self.lbl_status)
        layout.addStretch()

        self._connect_signals()

    def _connect_signals(self):
        self.btn_load.clicked.connect(self.load_requested.emit)
        # 核心修改：同时发射 mass 和 expected_peaks
        self.btn_calc.clicked.connect(
            lambda: self.calculate_requested.emit(self.spin_mass.value(), self.spin_peaks.value()))
        self.btn_extract.clicked.connect(lambda: self.extract_requested.emit(self.input_times.text()))
        self.btn_export_excel.clicked.connect(self.export_excel_requested.emit)
        self.btn_export_images.clicked.connect(self.export_images_requested.emit)

    def update_status(self, msg: str, is_error: bool = False):
        color = "#EF233C" if is_error else "#2B2F42"
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.lbl_status.setText(f"状态: {msg}")