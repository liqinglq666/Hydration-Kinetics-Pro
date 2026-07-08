from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
import numpy as np

from core.data_models import KineticsParameters


class ResultsPanel(QWidget):
    """分析结果展示面板。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultsPanel")
        self.metric_labels = {}
        self._init_ui()
        self._apply_styles()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._create_metric_summary())

        self.table = QTableWidget(16, 2)
        self.table.setHorizontalHeaderLabels(["特征物理量", "解析数值"])
        self._prepare_table(self.table)
        self.table.verticalHeader().setVisible(False)

        keys = [
            "t0 (h)",
            "Qmax (J/g)",
            "t50 (h)",
            "n (级数)",
            "K1 (成核)",
            "K2 (边界)",
            "K3 (扩散)",
            "R² (NG 拟合优度)",
            "R² (I 拟合优度)",
            "R² (D 拟合优度)",
            "alpha_1",
            "t_alpha_1 (h)",
            "alpha_2",
            "t_alpha_2 (h)",
            "Δalpha (机制转换区间)",
            "Δh (转换时间跨度)",
        ]

        for i, key in enumerate(keys):
            item = QTableWidgetItem(key)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

        self.table_periods = QTableWidget(3, 3)
        self.table_periods.setHorizontalHeaderLabels(["起点 (h)", "终点 (h)", "时长 (h)"])
        self.table_periods.setVerticalHeaderLabels(["休眠期", "加速期", "减速期"])
        self._prepare_table(self.table_periods)

        self.table_peaks = QTableWidget(0, 3)
        self.table_peaks.setHorizontalHeaderLabels(["特征峰", "时间 (h)", "速率 (mW/g)"])
        self._prepare_table(self.table_peaks)
        self.table_peaks.verticalHeader().setVisible(False)

        self.table_heat = QTableWidget(0, 2)
        self.table_heat.setHorizontalHeaderLabels(["目标龄期 (h)", "放热量 (J/g)"])
        self._prepare_table(self.table_heat)
        self.table_heat.verticalHeader().setVisible(False)

        layout.addWidget(self._create_section("K-D 动力学核心参数与评估", self.table))
        layout.addWidget(self._create_section("水化机制阶段时间特征", self.table_periods))
        layout.addWidget(self._create_section("放热速率特征峰提取", self.table_peaks))
        layout.addWidget(self._create_section("特定龄期累计热量提取", self.table_heat))

    def _create_metric_summary(self) -> QGroupBox:
        box = QGroupBox("关键结果摘要")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 12, 10, 10)
        box_layout.setSpacing(8)

        caption = QLabel("优先查看这些指标，再进入下方明细表复核。")
        caption.setObjectName("sectionCaption")
        box_layout.addWidget(caption)

        grid = QGridLayout()
        grid.setSpacing(8)
        metrics = [
            ("t0", "--", "h"),
            ("Qmax", "--", "J/g"),
            ("t50", "--", "h"),
            ("R² NG / I / D", "--", ""),
            ("Qmax 来源", "--", ""),
            ("Fallback", "--", ""),
        ]
        for idx, (name, value, unit) in enumerate(metrics):
            card = self._create_metric_card(name, value, unit)
            grid.addWidget(card, idx // 3, idx % 3)
        box_layout.addLayout(grid)
        return box

    def _create_metric_card(self, name: str, value: str, unit: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(2)

        label_name = QLabel(name)
        label_name.setObjectName("MetricName")
        label_value = QLabel(value)
        label_value.setObjectName("MetricValue")
        label_unit = QLabel(unit)
        label_unit.setObjectName("MetricUnit")

        card_layout.addWidget(label_name)
        card_layout.addWidget(label_value)
        card_layout.addWidget(label_unit)
        self.metric_labels[name] = label_value
        return card

    def _prepare_table(self, table: QTableWidget) -> None:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(30)
        table.horizontalHeader().setMinimumHeight(30)

    def _create_section(self, title: str, target_table: QTableWidget) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 12, 10, 10)
        box_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        caption = QLabel(self._section_caption(title))
        caption.setObjectName("sectionCaption")

        btn_copy = QPushButton("复制")
        btn_copy.setObjectName("copyButton")
        btn_copy.setFixedWidth(58)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(lambda: self._copy_table_to_clipboard(target_table, btn_copy))

        header_layout.addWidget(caption)
        header_layout.addStretch()
        header_layout.addWidget(btn_copy)
        box_layout.addLayout(header_layout)
        box_layout.addWidget(target_table)
        return box

    def _section_caption(self, title: str) -> str:
        captions = {
            "K-D 动力学核心参数与评估": "用于论文主参数表与模型质量快速检查",
            "水化机制阶段时间特征": "休眠期、加速期、减速期的时间划分",
            "放热速率特征峰提取": "自动识别的主峰与多峰特征",
            "特定龄期累计热量提取": "1 h、24 h、72 h 等指定龄期快速摘录",
        }
        return captions.get(title, "")

    def _copy_table_to_clipboard(self, table: QTableWidget, btn: QPushButton) -> None:
        rows = table.rowCount()
        cols = table.columnCount()
        has_v_header = table.verticalHeader().isVisible()

        text_lines = []
        header_data = []
        if has_v_header:
            header_data.append("阶段标识")
        for c in range(cols):
            h_item = table.horizontalHeaderItem(c)
            header_data.append(h_item.text() if h_item else "")
        text_lines.append("\t".join(header_data))

        for r in range(rows):
            row_data = []
            if has_v_header:
                v_item = table.verticalHeaderItem(r)
                row_data.append(v_item.text() if v_item else f"Row {r + 1}")

            for c in range(cols):
                item = table.item(r, c)
                row_data.append(item.text() if item else "")
            text_lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(text_lines))

        btn.setText("已复制")
        btn.setProperty("copied", True)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        QTimer.singleShot(1500, lambda: self._reset_button_state(btn))

    def _reset_button_state(self, btn: QPushButton) -> None:
        btn.setText("复制")
        btn.setProperty("copied", False)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def display_results(self, params: KineticsParameters) -> None:
        self._update_metric_summary(params)

        values = [
            params.t0_h,
            params.qmax_j_g,
            params.t50_h,
            params.n,
            params.k1,
            params.k2,
            params.k3,
            params.r2_ng,
            params.r2_i,
            params.r2_d,
            params.alpha_1,
            params.t_alpha_1_h,
            params.alpha_2,
            params.t_alpha_2_h,
            params.delta_alpha,
            params.delta_time_h,
        ]

        for i, val in enumerate(values):
            text = f"{val:.4e}" if i in [4, 5, 6] else f"{val:.4f}"
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, item)

        periods_data = [
            [0.0, params.t0_h, params.induction_duration_h],
            [params.t0_h, params.t_peak_h, params.accel_duration_h],
            [params.t_peak_h, params.t_end_h, params.decel_duration_h],
        ]
        for row in range(3):
            for col in range(3):
                item = QTableWidgetItem(f"{periods_data[row][col]:.2f}")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_periods.setItem(row, col, item)

        self.table_peaks.setRowCount(len(params.peaks))
        for i, (t_val, hf_val) in enumerate(params.peaks):
            item_name = QTableWidgetItem(f"Peak {i + 1}")
            item_t = QTableWidgetItem(f"{t_val:.2f}")
            item_hf = QTableWidgetItem(f"{hf_val:.4f}")
            for col, item in enumerate([item_name, item_t, item_hf]):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_peaks.setItem(i, col, item)

    def _update_metric_summary(self, params: KineticsParameters) -> None:
        method = getattr(params, "qmax_method", "unknown")
        method_label = {
            "manual_total_cumulative_heat_qinf": "Manual Q∞",
            "knudsen_linear_extrapolation": "Knudsen",
            "fallback_q_final_x_1.15": "Fallback",
        }.get(method, method)

        self.metric_labels["t0"].setText(f"{params.t0_h:.3f}")
        self.metric_labels["Qmax"].setText(f"{params.qmax_j_g:.2f}")
        self.metric_labels["t50"].setText(f"{params.t50_h:.2f}")
        self.metric_labels["R² NG / I / D"].setText(f"{params.r2_ng:.3f} / {params.r2_i:.3f} / {params.r2_d:.3f}")
        self.metric_labels["Qmax 来源"].setText(method_label)
        self.metric_labels["Fallback"].setText("YES" if getattr(params, "qmax_fallback_used", False) else "NO")

    def display_extracted_heat(self, times: np.ndarray, heats: np.ndarray) -> None:
        self.table_heat.setRowCount(len(times))
        for i in range(len(times)):
            item_t = QTableWidgetItem(f"{times[i]:.2f}")
            heat_text = "超出数据范围" if not np.isfinite(heats[i]) else f"{heats[i]:.2f}"
            item_h = QTableWidgetItem(heat_text)
            item_t.setFlags(item_t.flags() & ~Qt.ItemIsEditable)
            item_h.setFlags(item_h.flags() & ~Qt.ItemIsEditable)
            item_t.setTextAlignment(Qt.AlignCenter)
            item_h.setTextAlignment(Qt.AlignCenter)
            self.table_heat.setItem(i, 0, item_t)
            self.table_heat.setItem(i, 1, item_h)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#ResultsPanel {
                background: transparent;
                color: #1f2937;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                margin-top: 12px;
                padding: 10px;
                font-weight: 800;
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
            QLabel#sectionCaption {
                color: #6b7280;
                font-size: 12px;
                font-weight: 500;
            }
            QFrame#MetricCard {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 9px;
            }
            QLabel#MetricName {
                color: #6b7280;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#MetricValue {
                color: #111827;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#MetricUnit {
                color: #6b7280;
                font-size: 11px;
                font-weight: 500;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f9fafb;
                border: 1px solid #eef2f7;
                border-radius: 6px;
                color: #111827;
                gridline-color: #eef2f7;
                selection-background-color: #dbeafe;
                selection-color: #111827;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                color: #374151;
                padding: 5px;
                border: 0;
                border-bottom: 1px solid #e5e7eb;
                font-weight: 700;
            }
            QPushButton#copyButton {
                background: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#copyButton:hover {
                background: #eff6ff;
                border-color: #bfdbfe;
                color: #1d4ed8;
            }
            QPushButton#copyButton[copied="true"] {
                background: #ecfdf5;
                border-color: #a7f3d0;
                color: #047857;
            }
            """
        )
