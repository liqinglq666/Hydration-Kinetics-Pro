import os
import platform
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.async_workers import KineticsWorker
from gui.layouts.control_panel import ControlPanel
from gui.layouts.results_panel import ResultsPanel
from gui.plot_canvas import ScientificCanvas
from utils.logger import logger


class MainWindow(QMainWindow):
    """Hydration Kinetics Pro 主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hydration Kinetics Pro - Publication Edition")
        self.resize(1600, 980)
        self.current_data_path = None
        self.cached_hydration_data = None
        self.cached_params = None
        self.plot_buttons = {}
        self.plot_captions = {
            "raw": "热流与累计热量，优先用于检查原始曲线质量。",
            "knudsen": "Qmax 外推图，重点看线性区与 R²。",
            "linear": "K-D 三阶段线性化拟合，重点看 NG / I / D 分段质量。",
            "envelope": "机制速率包络，重点看 α1、α2 与控制阶段转换。",
        }
        self._init_ui()
        self._apply_window_styles()

    def _init_ui(self) -> None:
        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        self.control_panel = ControlPanel()
        self.results_panel = ResultsPanel()
        self.canvas = ScientificCanvas(plot_mode="raw")

        left_scroll = QScrollArea()
        left_scroll.setObjectName("SidebarScroll")
        left_scroll.setWidget(self.control_panel)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_scroll.setMinimumWidth(390)
        left_scroll.setMaximumWidth(430)

        self.results_card = QFrame()
        self.results_card.setObjectName("WorkspaceCard")
        results_layout = QVBoxLayout(self.results_card)
        results_layout.setContentsMargins(12, 10, 12, 12)
        results_layout.setSpacing(8)

        results_header = QHBoxLayout()
        results_title = QLabel("结果数据区")
        results_title.setObjectName("CardTitle")
        results_caption = QLabel("数据表是主视图：关键摘要、K-D 参数、阶段特征与指定龄期热量")
        results_caption.setObjectName("CardCaption")
        results_header.addWidget(results_title)
        results_header.addSpacing(12)
        results_header.addWidget(results_caption)
        results_header.addStretch()
        results_layout.addLayout(results_header)

        results_scroll = QScrollArea()
        results_scroll.setObjectName("ResultsScroll")
        results_scroll.setWidget(self.results_panel)
        results_scroll.setWidgetResizable(True)
        results_scroll.setFrameShape(QScrollArea.NoFrame)
        results_layout.addWidget(results_scroll, stretch=1)

        self.plot_card = QFrame()
        self.plot_card.setObjectName("WorkspaceCard")
        plot_layout = QVBoxLayout(self.plot_card)
        plot_layout.setContentsMargins(12, 10, 12, 12)
        plot_layout.setSpacing(8)

        plot_header = QHBoxLayout()
        plot_title = QLabel("图表折叠卡片")
        plot_title.setObjectName("CardTitle")
        self.plot_caption = QLabel(self.plot_captions["raw"])
        self.plot_caption.setObjectName("CardCaption")
        plot_header.addWidget(plot_title)
        plot_header.addSpacing(12)
        plot_header.addWidget(self.plot_caption)
        plot_header.addStretch()
        plot_layout.addLayout(plot_header)

        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(8)
        for mode, label in [
            ("raw", "① Raw Data"),
            ("knudsen", "② Knudsen"),
            ("linear", "③ K-D Regressions"),
            ("envelope", "④ Envelope"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("PlotAccordionButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.clicked.connect(lambda checked=False, m=mode: self._select_plot_card(m))
            self.plot_buttons[mode] = btn
            selector_layout.addWidget(btn)
        self.plot_buttons["raw"].setChecked(True)
        plot_layout.addLayout(selector_layout)
        plot_layout.addWidget(self.canvas, stretch=1)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setObjectName("RightSplitter")
        right_splitter.addWidget(self.results_card)
        right_splitter.addWidget(self.plot_card)
        right_splitter.setSizes([630, 340])
        right_splitter.setChildrenCollapsible(False)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setObjectName("MainSplitter")
        main_splitter.addWidget(left_scroll)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([410, 1190])
        main_splitter.setChildrenCollapsible(False)

        root_layout.addWidget(main_splitter)

        self.control_panel.load_requested.connect(self._handle_load)
        self.control_panel.calculate_requested.connect(self._handle_calc)
        self.control_panel.extract_requested.connect(self._handle_heat_extraction)
        self.control_panel.export_excel_requested.connect(self._handle_excel_export)
        self.control_panel.export_images_requested.connect(self._handle_image_export)

    def _select_plot_card(self, mode: str) -> None:
        for key, btn in self.plot_buttons.items():
            btn.setChecked(key == mode)
        self.plot_caption.setText(self.plot_captions.get(mode, ""))
        self.canvas.set_plot_mode(mode)

    def _handle_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择量热数据",
            "",
            "Data Files (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if path:
            self.current_data_path = Path(path)
            self.cached_hydration_data = None
            self.cached_params = None
            self.control_panel.update_status(f"文件就绪：{self.current_data_path.name}")
            self.control_panel.btn_calc.setEnabled(True)
            self.control_panel.btn_extract.setEnabled(False)
            self.control_panel.btn_export_excel.setEnabled(False)
            self.control_panel.btn_export_images.setEnabled(False)

    def _handle_calc(
        self,
        mass: float,
        expected_peaks: int,
        input_mode: str,
        use_manual_t0: bool,
        manual_t0_h: float,
        use_manual_qmax: bool,
        manual_qmax_total_j_g: float,
        allow_qmax_fallback: bool,
    ) -> None:
        if self.current_data_path is None:
            QMessageBox.warning(self, "缺少数据文件", "请先导入量热数据文件。")
            return

        self.control_panel.btn_calc.setEnabled(False)
        self.control_panel.btn_load.setEnabled(False)
        self.control_panel.btn_extract.setEnabled(False)
        self.control_panel.btn_export_excel.setEnabled(False)
        self.control_panel.btn_export_images.setEnabled(False)

        self.worker = KineticsWorker(
            self.current_data_path,
            mass,
            expected_peaks,
            input_mode,
            use_manual_t0=use_manual_t0,
            manual_t0_h=manual_t0_h,
            use_manual_qmax=use_manual_qmax,
            manual_qmax_total_j_g=manual_qmax_total_j_g,
            allow_qmax_fallback=allow_qmax_fallback,
        )
        self.worker.progress.connect(self.control_panel.update_status)
        self.worker.data_loaded.connect(self._on_data_loaded)
        self.worker.analysis_finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_data_loaded(self, data) -> None:
        self.cached_hydration_data = data
        self.control_panel.btn_extract.setEnabled(True)
        self.canvas.plot_hydration_data(data.time_h, data.heat_flow_mw_g, data.cumulative_heat_j_g)

        parser_warnings = getattr(data, "parser_warnings", [])
        if parser_warnings:
            QMessageBox.warning(
                self,
                "数据单位提醒",
                "\n\n".join(parser_warnings) + "\n\n本次不会拦截计算，程序将继续按照 GUI 当前选择的单位模式处理数据。",
            )

    def _on_finished(self, res) -> None:
        params, data = res
        self.cached_params = params
        self.results_panel.display_results(params)
        self.canvas.plot_hydration_data(data.time_h, data.heat_flow_mw_g, data.cumulative_heat_j_g, params=params)

        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
        self.control_panel.btn_extract.setEnabled(True)
        self.control_panel.btn_export_excel.setEnabled(True)
        self.control_panel.btn_export_images.setEnabled(True)
        self.control_panel.update_status("解析完成，可以提取数据或导出图表。")

    def _on_error(self, err_msg: str) -> None:
        self.control_panel.update_status("核心引擎执行异常", is_error=True)
        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
        self.control_panel.btn_extract.setEnabled(self.cached_hydration_data is not None)
        QMessageBox.critical(self, "计算失败", err_msg)

    def _handle_heat_extraction(self, times_str: str) -> None:
        if self.cached_hydration_data is None:
            QMessageBox.warning(self, "提取失败", "数据尚未完成解析，请先执行分析。")
            return
        try:
            parts = [part.strip() for part in re.split(r"[,，;；\s]+", times_str) if part.strip()]
            target_times = np.sort(np.array([float(part) for part in parts]))
            if len(target_times) == 0:
                raise ValueError("empty time list")
            heats = np.interp(
                target_times,
                self.cached_hydration_data.time_h,
                self.cached_hydration_data.cumulative_heat_j_g,
                left=np.nan,
                right=np.nan,
            )
            self.results_panel.display_extracted_heat(target_times, heats)
        except ValueError:
            QMessageBox.warning(self, "非法输入", "时间序列格式错误，请输入如: 1.0, 24, 72.5")

    def _handle_excel_export(self) -> None:
        default_name = (
            f"{self.current_data_path.stem}_Kinetics_Report.xlsx"
            if self.current_data_path
            else "Kinetics_Report.xlsx"
        )
        save_path, _ = QFileDialog.getSaveFileName(self, "保存主数据报表", default_name, "Excel Files (*.xlsx)")
        if not save_path:
            return

        try:
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                if self.cached_params:
                    self._write_qc_tables(writer)
                    self._write_kinetics_tables(writer)

                self._table_to_df(self.results_panel.table_periods, has_vertical_header=True).to_excel(
                    writer, sheet_name="水化阶段特征", index=False
                )
                self._table_to_df(self.results_panel.table_peaks).to_excel(
                    writer, sheet_name="放热峰特征提取", index=False
                )
                self._table_to_df(self.results_panel.table_heat).to_excel(
                    writer, sheet_name="特定龄期热量", index=False
                )

            if self.cached_params:
                self._write_origin_plot_data(save_path)

            self.control_panel.update_status("已生成数据报表、QC 追溯表与 Origin 绘图源数据。")
            self._open_system_folder(save_path)

        except Exception as e:
            QMessageBox.critical(self, "报表生成失败", f"Excel 写入失败:\n{str(e)}")

    def _r2_quality(self, r2_value: float, stage: str = "") -> tuple[str, str]:
        if r2_value is None or not np.isfinite(r2_value):
            return "Unknown", "R² 无法计算，请检查拟合窗口数据。"
        if r2_value >= 0.95:
            return "Excellent", "拟合优度很高，可作为主要定量结果。"
        if r2_value >= 0.85:
            return "Good", "拟合较好，可用于定量比较，但建议结合图形复核。"
        if r2_value >= 0.70:
            return "Caution", "拟合一般，建议在论文或报告中谨慎解释。"
        return "Low", f"{stage} 拟合偏低，建议复核数据质量、拟合窗口或机理适用性。"

    def _write_qc_tables(self, writer: pd.ExcelWriter) -> None:
        p = self.cached_params
        d = self.cached_hydration_data
        mix_name = self.current_data_path.stem if self.current_data_path else "Sample"

        qc_rows = [
            {"Item": "Sample", "Value": mix_name, "Interpretation": "样品或文件名"},
            {"Item": "Source File", "Value": str(self.current_data_path) if self.current_data_path else "-", "Interpretation": "原始数据路径"},
            {"Item": "Input Mode", "Value": getattr(p, "input_mode", getattr(d, "input_mode", "unknown")), "Interpretation": "total=总热流/总热量；normalized=已归一化 mW/g、J/g"},
            {"Item": "Detected Unit Mode", "Value": getattr(p, "detected_unit_mode", getattr(d, "detected_unit_mode", None)) or "not detected", "Interpretation": "由表头自动识别；为空说明表头单位不明确"},
            {"Item": "Sample Mass (g)", "Value": getattr(d, "sample_mass_g", 1.0), "Interpretation": "total 模式会用该质量归一化；normalized 模式仅记录，不再参与计算"},
            {"Item": "t0 Method", "Value": getattr(p, "t0_method", "auto_min_heat_flow"), "Interpretation": "auto_min_heat_flow=自动低谷识别；manual=用户手动指定"},
            {"Item": "Manual t0 (h)", "Value": getattr(p, "manual_t0_h", None) if getattr(p, "manual_t0_h", None) is not None else "-", "Interpretation": "用户手动指定的 K-D 起算时间"},
            {"Item": "Final t0 Used (h)", "Value": round(p.t0_h, 6), "Interpretation": "最终用于 α 与 K-D 拟合的 t0"},
            {"Item": "Q(t0) (J/g)", "Value": round(getattr(p, "q_at_t0_j_g", 0.0), 6), "Interpretation": "手动 Q∞ 会先扣除该值，得到 t0 后有效 Qmax"},
            {"Item": "Manual Q∞ Total (J/g)", "Value": getattr(p, "manual_qmax_total_j_g", None) if getattr(p, "manual_qmax_total_j_g", None) is not None else "-", "Interpretation": "从实验起点计的手动总累计极限热量"},
            {"Item": "Qmax Method", "Value": getattr(p, "qmax_method", "unknown"), "Interpretation": "manual、Knudsen 线性外推或 fallback 补偿策略"},
            {"Item": "Qmax Fallback Allowed", "Value": "YES" if getattr(p, "qmax_fallback_allowed", True) else "NO", "Interpretation": "NO 时自动外推失败会直接报错"},
            {"Item": "Qmax Fallback Used", "Value": "YES" if getattr(p, "qmax_fallback_used", False) else "NO", "Interpretation": "YES 表示 Qmax 不是直接来自手动值或可靠线性外推"},
            {"Item": "Effective Qmax after t0 (J/g)", "Value": round(p.qmax_j_g, 6), "Interpretation": "最终用于 α=[Q(t)-Q(t0)]/Qmax 的分母"},
            {"Item": "Total Q∞ Equivalent (J/g)", "Value": round(getattr(p, "qmax_total_j_g", p.qmax_j_g), 6), "Interpretation": "从实验起点计的等效 Q∞=Q(t0)+effective Qmax"},
            {"Item": "t50 (h)", "Value": round(p.t50_h, 6), "Interpretation": "t0 后达到 effective Qmax/2 的特征时间"},
        ]
        pd.DataFrame(qc_rows).to_excel(writer, sheet_name="QC_Traceability", index=False)

        parser_warnings = list(getattr(d, "parser_warnings", []))
        if parser_warnings:
            pd.DataFrame(
                [{"No.": idx + 1, "Parser Warning": msg} for idx, msg in enumerate(parser_warnings)]
            ).to_excel(writer, sheet_name="QC_Parser_Warnings", index=False)

        r2_rows = []
        for stage, value in [
            ("Knudsen Qmax", getattr(p, "r2_knudsen", np.nan)),
            ("NG stage", p.r2_ng),
            ("I stage", p.r2_i),
            ("D stage", p.r2_d),
        ]:
            quality, note = self._r2_quality(float(value), stage=stage)
            if stage == "Knudsen Qmax" and getattr(p, "qmax_fallback_used", False):
                quality = "Fallback"
                note = "Knudsen 拟合触发 fallback；Qmax 使用 Q_final * 1.15，R² 仅反映拟合窗口线性程度。"
            if stage == "Knudsen Qmax" and getattr(p, "qmax_method", "") == "manual_total_cumulative_heat_qinf":
                quality = "Manual"
                note = "Qmax 由用户手动指定 Q∞ 决定；Knudsen R² 仅作为后期线性参考，不决定 Qmax。"
            r2_rows.append({"Fit Object": stage, "R2": round(float(value), 6) if np.isfinite(value) else "-", "Quality": quality, "Interpretation": note})
        pd.DataFrame(r2_rows).to_excel(writer, sheet_name="QC_R2_Review", index=False)

        warnings = list(getattr(p, "warnings", []))
        if not warnings:
            warnings = ["No solver warning was recorded."]
        pd.DataFrame(
            [{"No.": idx + 1, "Warning": msg} for idx, msg in enumerate(warnings)]
        ).to_excel(writer, sheet_name="QC_Warnings", index=False)

    def _write_kinetics_tables(self, writer: pd.ExcelWriter) -> None:
        p = self.cached_params
        mix_name = self.current_data_path.stem if self.current_data_path else "Sample"

        r2_knudsen = round(getattr(p, "r2_knudsen", 0.0), 5)
        knudsen_eq = f"1/Q={1 / p.qmax_j_g:.5f}+{p.t50_h / p.qmax_j_g:.5f}/(t-t0)"
        pd.DataFrame(
            [
                {
                    "Mixture": mix_name,
                    "Q(t0)/(J·g-1)": round(getattr(p, "q_at_t0_j_g", 0.0), 4),
                    "Effective Qmax after t0/(J·g-1)": round(p.qmax_j_g, 2),
                    "Total Q∞ equivalent/(J·g-1)": round(getattr(p, "qmax_total_j_g", p.qmax_j_g), 2),
                    "t50/h": round(p.t50_h, 2),
                    "1/Q=1/Qmax+t50/Qmax(t-t0)": knudsen_eq,
                    "R2": r2_knudsen,
                    "Qmax Method": getattr(p, "qmax_method", "unknown"),
                    "Fallback Used": "YES" if getattr(p, "qmax_fallback_used", False) else "NO",
                }
            ]
        ).to_excel(writer, sheet_name="Tab5_Knudsen", index=False)

        int_ng = p.n * np.log(p.k1)
        eq_ng = f"ln[-ln(1-alpha)]={p.n:.4f}ln(t-t0){'+' if int_ng >= 0 else '-'}{abs(int_ng):.4f}"
        int_i = np.log(p.k2)
        eq_i = f"ln[1-(1-alpha)^(1/3)]=ln(t-t0){'+' if int_i >= 0 else '-'}{abs(int_i):.4f}"
        int_d = np.log(p.k3)
        eq_d = f"2ln[1-(1-alpha)^(1/3)]=ln(t-t0){'+' if int_d >= 0 else '-'}{abs(int_d):.4f}"

        pd.DataFrame(
            [
                {
                    "Mixture": mix_name,
                    "F_NG equation": eq_ng,
                    "R2 (NG)": round(p.r2_ng, 4),
                    "NG Quality": self._r2_quality(p.r2_ng, "NG")[0],
                    "F_I equation": eq_i,
                    "R2 (I)": round(p.r2_i, 4),
                    "I Quality": self._r2_quality(p.r2_i, "I")[0],
                    "F_D equation": eq_d,
                    "R2 (D)": round(p.r2_d, 4),
                    "D Quality": self._r2_quality(p.r2_d, "D")[0],
                }
            ]
        ).to_excel(writer, sheet_name="Tab6_KD_Eqs", index=False)

        pd.DataFrame(
            [
                {
                    "Mixture": mix_name,
                    "t0 method": getattr(p, "t0_method", "auto_min_heat_flow"),
                    "t0/h": round(p.t0_h, 4),
                    "Qmax method": getattr(p, "qmax_method", "unknown"),
                    "n": round(p.n, 4),
                    "K'1": float(p.k1),
                    "K'2": float(p.k2),
                    "K'3": float(p.k3),
                    "alpha_1": round(p.alpha_1, 4),
                    "alpha_2": round(p.alpha_2, 4),
                    "delta_alpha": round(p.delta_alpha, 4),
                }
            ]
        ).to_excel(writer, sheet_name="Tab7_KD_Params", index=False)

    def _write_origin_plot_data(self, save_path: str) -> None:
        origin_path = str(Path(save_path).parent / f"{Path(save_path).stem}_Origin_Plot_Data.xlsx")
        with pd.ExcelWriter(origin_path, engine="openpyxl") as writer_origin:
            if self.cached_params.origin_knudsen:
                pd.DataFrame(self.cached_params.origin_knudsen).to_excel(
                    writer_origin, sheet_name="1_Knudsen拟合", index=False
                )
            if self.cached_params.origin_kd_linear:
                dict_linear = self.cached_params.origin_kd_linear
                max_len = max([len(v) for v in dict_linear.values()] + [0])
                padded_linear = {
                    col: np.pad(arr.astype(float), (0, max_len - len(arr)), constant_values=np.nan)
                    for col, arr in dict_linear.items()
                }
                pd.DataFrame(padded_linear).to_excel(
                    writer_origin, sheet_name="2_KD分段散点拟合", index=False
                )
            if self.cached_params.origin_rates:
                pd.DataFrame(self.cached_params.origin_rates).to_excel(
                    writer_origin, sheet_name="3_理论速率包络线", index=False
                )

    def _handle_image_export(self) -> None:
        default_dir = str(self.current_data_path.parent) if self.current_data_path else ""
        dir_path = QFileDialog.getExistingDirectory(self, "选择科研图像输出目录", default_dir)
        if not dir_path:
            return

        try:
            self.canvas.save_individual_plots(dir_path)
            self.control_panel.update_status("高分辨率图像导出成功。")
            self._open_system_folder(dir_path)
        except Exception as e:
            QMessageBox.critical(self, "图像导出失败", f"Matplotlib 渲染导出失败:\n{str(e)}")

    def _table_to_df(self, table: QTableWidget, has_vertical_header: bool = False) -> pd.DataFrame:
        rows, cols = table.rowCount(), table.columnCount()
        headers = [table.horizontalHeaderItem(i).text() for i in range(cols)]
        data = []
        for r in range(rows):
            row_data = (
                [table.verticalHeaderItem(r).text() if table.verticalHeaderItem(r) else f"Row {r + 1}"]
                if has_vertical_header
                else []
            )
            row_data.extend([table.item(r, c).text() if table.item(r, c) else "" for c in range(cols)])
            data.append(row_data)
        if has_vertical_header:
            headers = ["阶段标识"] + headers
        return pd.DataFrame(data, columns=headers)

    def _open_system_folder(self, target_path: str) -> None:
        path = Path(target_path)
        folder_path = str(path.parent if path.is_file() else path)
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            logger.warning(f"无法打开资源管理器: {str(e)}")

    def _apply_window_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background-color: #f6f8fb;
            }
            QScrollArea#SidebarScroll, QScrollArea#ResultsScroll {
                background: transparent;
                border: none;
            }
            QFrame#WorkspaceCard {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            QLabel#CardTitle {
                color: #111827;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#CardCaption {
                color: #6b7280;
                font-size: 12px;
            }
            QPushButton#PlotAccordionButton {
                background: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton#PlotAccordionButton:hover {
                background: #eff6ff;
                border-color: #bfdbfe;
                color: #1d4ed8;
            }
            QPushButton#PlotAccordionButton:checked {
                background: #2563eb;
                border-color: #1d4ed8;
                color: #ffffff;
            }
            QSplitter::handle {
                background: #e5e7eb;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal {
                width: 6px;
            }
            QSplitter::handle:vertical {
                height: 6px;
            }
            """
        )
