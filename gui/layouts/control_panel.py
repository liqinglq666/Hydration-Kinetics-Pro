from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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
        self.setObjectName("ControlPanel")
        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QLabel("Hydration Kinetics Pro")
        header.setObjectName("panelTitle")
        subtitle = QLabel("等温量热 · K-D 动力学 · QC 追溯")
        subtitle.setObjectName("panelSubtitle")

        self.btn_load = QPushButton("导入量热数据  CSV / XLSX")
        self.btn_load.setObjectName("primaryButton")
        self.btn_load.setMinimumHeight(36)
        self.btn_load.setCursor(Qt.PointingHandCursor)

        self.btn_calc = QPushButton("执行动力学全解析")
        self.btn_calc.setObjectName("accentButton")
        self.btn_calc.setMinimumHeight(38)
        self.btn_calc.setCursor(Qt.PointingHandCursor)
        self.btn_calc.setEnabled(False)

        self.spin_mass = QDoubleSpinBox()
        self.spin_mass.setRange(0.01, 1000.0)
        self.spin_mass.setValue(1.00)
        self.spin_mass.setSingleStep(0.1)
        self.spin_mass.setDecimals(3)
        self.spin_mass.setToolTip("total 模式下用于归一化。建议填写胶凝材料质量，而不是包含水、砂、纤维的总试样质量。")

        self.spin_peaks = QSpinBox()
        self.spin_peaks.setRange(1, 4)
        self.spin_peaks.setValue(1)
        self.spin_peaks.setToolTip("存在多峰水化行为时可提高该值；普通 OPC 或示例数据一般为 1。")

        self.combo_input_mode = QComboBox()
        self.combo_input_mode.addItem("总热流 mW / 总热量 J，需要按质量归一化", "total")
        self.combo_input_mode.addItem("已归一化 mW/g / J/g，不再除以质量", "normalized")
        self.combo_input_mode.setToolTip("程序会尊重这里的选择继续计算；若表头单位看起来不一致，只弹出提醒，不再拦截。")

        data_card = QGroupBox("① 数据与单位")
        data_layout = QVBoxLayout(data_card)
        data_layout.setSpacing(8)
        data_layout.addWidget(self.btn_load)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        mass_form = QFormLayout()
        mass_form.setContentsMargins(0, 0, 0, 0)
        mass_form.setLabelAlignment(Qt.AlignLeft)
        mass_form.addRow("有效质量 g", self.spin_mass)
        peak_form = QFormLayout()
        peak_form.setContentsMargins(0, 0, 0, 0)
        peak_form.setLabelAlignment(Qt.AlignLeft)
        peak_form.addRow("特征峰数", self.spin_peaks)
        top_row.addLayout(mass_form, stretch=3)
        top_row.addLayout(peak_form, stretch=2)
        data_layout.addLayout(top_row)

        unit_form = QFormLayout()
        unit_form.setContentsMargins(0, 0, 0, 0)
        unit_form.addRow("输入单位", self.combo_input_mode)
        data_layout.addLayout(unit_form)

        self.chk_manual_t0 = QCheckBox("手动 t0")
        self.chk_manual_t0.setToolTip("仅当自动 t0 明显偏离诱导期低谷或加速期起点时启用。")
        self.spin_manual_t0 = QDoubleSpinBox()
        self.spin_manual_t0.setRange(0.0, 10000.0)
        self.spin_manual_t0.setDecimals(4)
        self.spin_manual_t0.setSingleStep(0.1)
        self.spin_manual_t0.setSuffix(" h")
        self.spin_manual_t0.setEnabled(False)
        self.spin_manual_t0.setToolTip("K-D 动力学起算时间，应位于初始溶解峰之后、主加速峰之前。")

        self.chk_manual_qmax = QCheckBox("手动 Q∞")
        self.chk_manual_qmax.setToolTip("填写从实验起点计的最终累计热量 Q∞，单位 J/g。程序会自动扣除 Q(t0)，得到 t0 后有效 Qmax。")
        self.spin_manual_qmax = QDoubleSpinBox()
        self.spin_manual_qmax.setRange(0.001, 100000.0)
        self.spin_manual_qmax.setDecimals(4)
        self.spin_manual_qmax.setSingleStep(10.0)
        self.spin_manual_qmax.setSuffix(" J/g")
        self.spin_manual_qmax.setEnabled(False)
        self.spin_manual_qmax.setToolTip("建议来自长龄期累计热量、理论极限热量或可靠文献。必须大于当前数据终点累计热量。")

        self.chk_allow_qmax_fallback = QCheckBox("允许 Qmax 自动失败时使用 Q_final × 1.15 fallback")
        self.chk_allow_qmax_fallback.setChecked(True)
        self.chk_allow_qmax_fallback.setToolTip("关闭后，若 Knudsen 外推失效且未手动指定 Q∞，程序会直接报错，避免低置信度结果进入论文表格。")

        anchor_card = QGroupBox("② 论文级锚点控制")
        anchor_layout = QVBoxLayout(anchor_card)
        anchor_layout.setSpacing(8)
        t0_row = QHBoxLayout()
        t0_row.addWidget(self.chk_manual_t0, stretch=2)
        t0_row.addWidget(self.spin_manual_t0, stretch=3)
        qmax_row = QHBoxLayout()
        qmax_row.addWidget(self.chk_manual_qmax, stretch=2)
        qmax_row.addWidget(self.spin_manual_qmax, stretch=3)
        anchor_layout.addLayout(t0_row)
        anchor_layout.addLayout(qmax_row)
        anchor_layout.addWidget(self.chk_allow_qmax_fallback)
        anchor_layout.addWidget(self.btn_calc)

        self.input_times = QLineEdit("1, 10, 24, 48, 60, 72")
        self.input_times.setPlaceholderText("如: 1, 24, 72")
        self.btn_extract = QPushButton("提取特定龄期热量")
        self.btn_extract.setObjectName("secondaryButton")
        self.btn_extract.setMinimumHeight(34)
        self.btn_extract.setCursor(Qt.PointingHandCursor)
        self.btn_extract.setEnabled(False)

        extract_card = QGroupBox("③ 工程辅助提取")
        extract_layout = QFormLayout(extract_card)
        extract_layout.setSpacing(8)
        extract_layout.addRow("目标时间 h", self.input_times)
        extract_layout.addRow("", self.btn_extract)

        self.btn_export_excel = QPushButton("导出 Excel 数据报表")
        self.btn_export_excel.setObjectName("outputButton")
        self.btn_export_excel.setMinimumHeight(36)
        self.btn_export_excel.setCursor(Qt.PointingHandCursor)
        self.btn_export_excel.setEnabled(False)

        self.btn_export_images = QPushButton("保存科研图像")
        self.btn_export_images.setObjectName("outputButton")
        self.btn_export_images.setMinimumHeight(36)
        self.btn_export_images.setCursor(Qt.PointingHandCursor)
        self.btn_export_images.setEnabled(False)

        output_card = QGroupBox("④ 科研成果输出")
        output_layout = QVBoxLayout(output_card)
        output_layout.setSpacing(8)
        output_layout.addWidget(self.btn_export_excel)
        output_layout.addWidget(self.btn_export_images)

        self.lbl_status = QLabel("等待载入")
        self.lbl_status.setObjectName("statusPill")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setMinimumHeight(34)
        self.lbl_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(data_card)
        layout.addWidget(anchor_card)
        layout.addWidget(extract_card)
        layout.addWidget(output_card)
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
        self.lbl_status.setProperty("state", "error" if is_error else "normal")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
        self.lbl_status.setText(f"状态：{msg}")

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget#ControlPanel {
                background: transparent;
                color: #1f2937;
                font-size: 13px;
            }
            QLabel#panelTitle {
                color: #111827;
                font-size: 20px;
                font-weight: 800;
                padding: 2px 0 0 2px;
            }
            QLabel#panelSubtitle {
                color: #6b7280;
                font-size: 12px;
                padding: 0 0 4px 2px;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                margin-top: 12px;
                padding: 12px 10px 10px 10px;
                font-weight: 700;
                color: #111827;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: #f6f8fb;
                color: #374151;
            }
            QLabel {
                color: #374151;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                min-height: 28px;
                padding: 2px 6px;
                color: #111827;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #2563eb;
            }
            QCheckBox {
                color: #374151;
                spacing: 7px;
            }
            QPushButton {
                border-radius: 7px;
                padding: 6px 10px;
                font-weight: 700;
            }
            QPushButton#primaryButton {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
            }
            QPushButton#primaryButton:hover {
                background: #dbeafe;
            }
            QPushButton#accentButton {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
            }
            QPushButton#accentButton:hover {
                background: #1d4ed8;
            }
            QPushButton#secondaryButton, QPushButton#outputButton {
                background: #f9fafb;
                color: #111827;
                border: 1px solid #d1d5db;
            }
            QPushButton#secondaryButton:hover, QPushButton#outputButton:hover {
                background: #f3f4f6;
                border-color: #9ca3af;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                color: #9ca3af;
                border: 1px solid #e5e7eb;
            }
            QLabel#statusPill {
                background: #ecfdf5;
                color: #065f46;
                border: 1px solid #a7f3d0;
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 700;
            }
            QLabel#statusPill[state="error"] {
                background: #fef2f2;
                color: #991b1b;
                border: 1px solid #fecaca;
            }
            """
        )
