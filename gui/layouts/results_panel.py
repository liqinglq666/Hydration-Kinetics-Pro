from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QHeaderView, QLabel, QPushButton, QApplication)
from PySide6.QtCore import Qt, QTimer
import numpy as np

from core.data_models import KineticsParameters


class ResultsPanel(QWidget):
    """
    分析结果展示面板。
    提供多维度数据表格，并内建一键 TSV 格式系统剪贴板导出流。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ==========================================
        # 1. 核心参数表
        # ==========================================
        self.table = QTableWidget(16, 2)
        self.table.setHorizontalHeaderLabels(['特征物理量', '解析数值'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

        keys = [
            't0 (h)', 'Qmax (J/g)', 't50 (h)',
            'n (级数)', 'K1 (成核)', 'K2 (边界)', 'K3 (扩散)',
            'R² (NG 拟合优度)', 'R² (I 拟合优度)', 'R² (D 拟合优度)',
            'alpha_1', 't_alpha_1 (h)', 'alpha_2', 't_alpha_2 (h)',
            'Δα (机制转换区间)', 'Δh (转换时间跨度)'
        ]

        for i, key in enumerate(keys):
            item = QTableWidgetItem(key)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

        # ==========================================
        # 2. 水化阶段表
        # ==========================================
        self.table_periods = QTableWidget(3, 3)
        self.table_periods.setHorizontalHeaderLabels(['起点(h)', '终点(h)', '时长(h)'])
        self.table_periods.setVerticalHeaderLabels(['休眠期', '加速期', '减速期'])
        self.table_periods.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # ==========================================
        # 3. 特征峰表
        # ==========================================
        self.table_peaks = QTableWidget(0, 3)
        self.table_peaks.setHorizontalHeaderLabels(['特征峰', '时间 (h)', '速率 (mW/g)'])
        self.table_peaks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_peaks.verticalHeader().setVisible(False)

        # ==========================================
        # 4. 特定龄期热量表
        # ==========================================
        self.table_heat = QTableWidget(0, 2)
        self.table_heat.setHorizontalHeaderLabels(['目标龄期 (h)', '放热量 (J/g)'])
        self.table_heat.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_heat.verticalHeader().setVisible(False)

        # ==========================================
        # 将带有复制按钮的标题栏与表格组合注入主布局
        # ==========================================
        layout.addLayout(self._create_header_with_copy("<b>K-D 动力学核心参数与评估</b>", self.table))
        layout.addWidget(self.table)
        layout.addSpacing(10)

        layout.addLayout(self._create_header_with_copy("<b>水化机制阶段时间特征</b>", self.table_periods))
        layout.addWidget(self.table_periods)
        layout.addSpacing(10)

        layout.addLayout(self._create_header_with_copy("<b>放热速率特征峰提取</b>", self.table_peaks))
        layout.addWidget(self.table_peaks)
        layout.addSpacing(10)

        layout.addLayout(self._create_header_with_copy("<b>特定龄期累积热量提取</b>", self.table_heat))
        layout.addWidget(self.table_heat)

    def _create_header_with_copy(self, title_html: str, target_table: QTableWidget) -> QHBoxLayout:
        """
        私有辅助方法：生成带有独立复制按钮的横向布局。
        利用 Lambda 闭包隔离每个按钮的作用域。
        """
        h_layout = QHBoxLayout()
        lbl = QLabel(title_html)

        btn_copy = QPushButton("📋 复制表格")
        btn_copy.setFixedWidth(80)
        btn_copy.setCursor(Qt.PointingHandCursor)
        self._set_button_style(btn_copy, is_success=False)

        # 绑定点击事件，将当前表格实例传入复制引擎
        btn_copy.clicked.connect(lambda: self._copy_table_to_clipboard(target_table, btn_copy))

        h_layout.addWidget(lbl)
        h_layout.addStretch()
        h_layout.addWidget(btn_copy)

        return h_layout

    def _set_button_style(self, btn: QPushButton, is_success: bool) -> None:
        """统一管理按钮的状态样式映射"""
        if is_success:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #d3f9d8;
                    border: 1px solid #b2f2bb;
                    border-radius: 4px;
                    padding: 2px 5px;
                    font-size: 11px;
                    color: #2b8a3e;
                    font-weight: bold;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 2px 5px;
                    font-size: 11px;
                    color: #495057;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                }
            """)

    def _copy_table_to_clipboard(self, table: QTableWidget, btn: QPushButton) -> None:
        """
        底层复制引擎：抓取 Data Model 并以 TSV (Tab-Separated Values) 格式注入系统剪贴板。
        确保直接 Ctrl+V 到 Excel/Origin 时行列绝对对齐。
        """
        rows = table.rowCount()
        cols = table.columnCount()
        has_v_header = table.verticalHeader().isVisible()

        text_lines = []

        # 1. 组装表头
        header_data = []
        if has_v_header:
            header_data.append("阶段标识")
        for c in range(cols):
            h_item = table.horizontalHeaderItem(c)
            header_data.append(h_item.text() if h_item else "")
        text_lines.append("\t".join(header_data))

        # 2. 组装数据矩阵
        for r in range(rows):
            row_data = []
            if has_v_header:
                v_item = table.verticalHeaderItem(r)
                row_data.append(v_item.text() if v_item else f"Row {r + 1}")

            for c in range(cols):
                item = table.item(r, c)
                row_data.append(item.text() if item else "")
            text_lines.append("\t".join(row_data))

        # 3. 推送至系统剪贴板
        final_text = "\n".join(text_lines)
        QApplication.clipboard().setText(final_text)

        # 4. UI 视觉正反馈
        btn.setText("✅ 已复制")
        self._set_button_style(btn, is_success=True)

        # 定时 1.5 秒后重置按钮状态，保证可重复交互性
        QTimer.singleShot(1500, lambda: self._reset_button_state(btn))

    def _reset_button_state(self, btn: QPushButton) -> None:
        """恢复按钮为默认状态"""
        btn.setText("📋 复制表格")
        self._set_button_style(btn, is_success=False)

    def display_results(self, params: KineticsParameters) -> None:
        values = [
            params.t0_h, params.qmax_j_g, params.t50_h,
            params.n, params.k1, params.k2, params.k3,
            params.r2_ng, params.r2_i, params.r2_d,
            params.alpha_1, params.t_alpha_1_h, params.alpha_2, params.t_alpha_2_h,
            params.delta_alpha, params.delta_time_h
        ]

        for i, val in enumerate(values):
            # 动力学速率常数段(K1, K2, K3)使用科学计数法渲染
            if i in [4, 5, 6]:
                text = f"{val:.4e}"
            else:
                text = f"{val:.4f}"

            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, item)

        periods_data = [
            [0.0, params.t0_h, params.induction_duration_h],
            [params.t0_h, params.t_peak_h, params.accel_duration_h],
            [params.t_peak_h, params.t_end_h, params.decel_duration_h]
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

    def display_extracted_heat(self, times: np.ndarray, heats: np.ndarray) -> None:
        self.table_heat.setRowCount(len(times))
        for i in range(len(times)):
            item_t = QTableWidgetItem(f"{times[i]:.2f}")
            item_h = QTableWidgetItem(f"{heats[i]:.2f}")
            item_t.setFlags(item_t.flags() & ~Qt.ItemIsEditable)
            item_h.setFlags(item_h.flags() & ~Qt.ItemIsEditable)
            self.table_heat.setItem(i, 0, item_t)
            self.table_heat.setItem(i, 1, item_h)