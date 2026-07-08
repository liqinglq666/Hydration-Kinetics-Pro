from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ControlPanel(QWidget):
    load_requested = Signal()
    calculate_requested = Signal(float, int, str, bool, float, bool, float, bool)
    extract_requested = Signal(str)
    export_excel_requested = Signal()
    export_images_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.btn_load = QPushButton("导入量热数据 (CSV/XLSX)")
        self.btn_calc = QPushButton("执行动力学全解析")
        self.btn_calc.setEnabled(False)

        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("有效质量 (g):"))
        self.spin_mass = QDoubleSpinBox()
        self.spin_mass.setRange(0.01, 1000.0)
        self.spin_mass.setValue(1.00)
        self.spin_mass.setSingleStep(0.1)
        self.spin_mass.setToolTip("total 模式下用于归一化。建议填写胶凝材料质量，而不是包含水、砂、纤维的总试样质量。")
        param_layout.addWidget(self.spin_mass)

        param_layout.addSpacing(10)
        param_layout.addWidget(QLabel("预期特征峰数:"))
        self.spin_peaks = QSpinBox()
        self.spin_peaks.setRange(1, 4)
        self.spin_peaks.setValue(1)
        param_layout.addWidget(self.spin_peaks)

        unit_layout = QVBoxLayout()
        unit_layout.addWidget(QLabel("<b>输入数据单位</b>"))
        self.combo_input_mode = QComboBox()
        self.combo_input_mode.addItem("总热流 mW / 总热量 J，需要按质量归一化", "total")
        self.combo_input_mode.addItem("已归一化 mW/g / J/g，不再除以质量", "normalized")
        self.combo_input_mode.setToolTip("务必按仪器导出单位选择。选错会导致 Qmax、速率常数和水化度整体失真。")
        unit_layout.addWidget(self.combo_input_mode)

        anchor_layout = QVBoxLayout()
        anchor_layout.addWidget(QLabel("<b>论文级锚点控制</b>"))

        t0_layout = QHBoxLayout()
        self.chk_manual_t0 = QCheckBox("手动 t0")
        self.chk_manual_t0.setToolTip("仅当自动 t0 明显偏离诱导期低谷或加速期起点时启用。")
        self.spin_manual_t0 = QDoubleSpinBox()
        self.spin_manual_t0.setRange(0.0, 10000.0)
        self.spin_manual_t0.setDecimals(4)
        self.spin_manual_t0.setSingleStep(0.1)
        self.spin_manual_t0.setSuffix(" h")
        self.spin_manual_t0.setEnabled(False)
        self.spin_manual_t0.setToolTip("K-D 动力学起算时间，应位于初始溶解峰之后、主加速峰之前。")
        t0_layout.addWidget(self.chk_manual_t0)
        t0_layout.addWidget(self.spin_manual_t0)
        anchor_layout.addLayout(t0_layout)

        qmax_layout = QHBoxLayout()
        self.chk_manual_qmax = QCheckBox("手动 Q∞")
        self.chk_manual_qmax.setToolTip("填写从实验起点计的最终累计热量 Q∞，单位 J/g。程序会自动扣除 Q(t0)，得到 t0 后有效 Qmax。")
        self.spin_manual_qmax = QDoubleSpinBox()
        self.spin_manual_qmax.setRange(0.001, 100000.0)
        self.spin_manual_qmax.setDecimals(4)
        self.spin_manual_qmax.setSingleStep(10.0)
        self.spin_manual_qmax.setSuffix(" J/g")
        self.spin_manual_qmax.setEnabled(False)
        self.spin_manual_qmax.setToolTip("建议来自长龄期累计热量、理论极限热量或可靠文献。必须大于当前数据终点累计热量。")
        qmax_layout.addWidget(self.chk_manual_qmax)
        qmax_layout.addWidget(self.spin_manual_qmax)
        anchor_layout.addLayout(qmax_layout)

        self.chk_allow_qmax_fallback = QCheckBox("允许自动 Qmax 失败时使用 Q_final × 1.15 fallback")
        self.chk_allow_qmax_fallback.setChecked(True)
        self.chk_allow_qmax_fallback.setToolTip("关闭后，若 Knudsen 外推失效且未手动指定 Q∞，程序会直接报错，避免低置信度结果进入论文表格。")
        anchor_layout.addWidget(self.chk_allow_qmax_fallback)

        extract_layout = QHBoxLayout()
        extract_layout.addWidget(QLabel("目标时间 (h):"))
        self.input_times = QLineEdit("1, 10, 24, 48, 60, 72")
        self.input_times.setPlaceholderText("如: 1, 24, 72")
        extract_layout.addWidget(self.input_times)

        self.btn_extract = QPushButton("提取特定龄期热量")
        self.btn_extract.setEnabled(False)

        self.btn_export_excel = QPushButton("导出 Excel 数据报表")
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setStyleSheet(
            "background-color: #f8f9fa; font-weight: bold; border: 1px solid #ced4da; padding: 5px;"
        )

        self.btn_export_images = QPushButton("保存科研图像")
        self.btn_export_images.setEnabled(False)
        self.btn_export_images.setStyleSheet(
            "background-color: #f8f9fa; font-weight: bold; border: 1px solid #ced4da; padding: 5px;"
        )

        self.lbl_status = QLabel("状态: 等待载入")
        self.lbl_status.setStyleSheet("color: #6c757d; font-weight: bold;")

        layout.addWidget(self.btn_load)
        layout.addLayout(param_layout)
        layout.addLayout(unit_layout)
        layout.addSpacing(8)
        layout.addLayout(anchor_layout)
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
        self.chk_manual_t0.toggled.connect(self.spin_manual_t0.setEnabled)
        self.chk_manual_qmax.toggled.connect(self.spin_manual_qmax.setEnabled)
        self.btn_calc.clicked.connect(
            lambda: self.calculate_requested.emit(
                self.spin_mass.value(),
                self.spin_peaks.value(),
                self.combo_input_mode.currentData(),
                self.chk_manual_t0.isChecked(),
                self.spin_manual_t0.value(),
                self.chk_manual_qmax.isChecked(),
                self.spin_manual_qmax.value(),
                self.chk_allow_qmax_fallback.isChecked(),
            )
        )
        self.btn_extract.clicked.connect(lambda: self.extract_requested.emit(self.input_times.text()))
        self.btn_export_excel.clicked.connect(self.export_excel_requested.emit)
        self.btn_export_images.clicked.connect(self.export_images_requested.emit)

    def update_status(self, msg: str, is_error: bool = False):
        color = "#EF233C" if is_error else "#2B2F42"
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.lbl_status.setText(f"状态: {msg}")
