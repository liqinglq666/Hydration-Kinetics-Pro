import os
import platform
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
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
        self.resize(1450, 950)
        self.current_data_path = None
        self.cached_hydration_data = None
        self.cached_params = None
        self._init_ui()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.control_panel = ControlPanel()
        self.results_panel = ResultsPanel()
        self.canvas = ScientificCanvas()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.addWidget(self.control_panel)
        left_layout.addWidget(self.results_panel)
        left_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidget(left_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(380)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        layout.addWidget(scroll_area, stretch=2)
        layout.addWidget(self.canvas, stretch=7)

        self.control_panel.load_requested.connect(self._handle_load)
        self.control_panel.calculate_requested.connect(self._handle_calc)
        self.control_panel.extract_requested.connect(self._handle_heat_extraction)
        self.control_panel.export_excel_requested.connect(self._handle_excel_export)
        self.control_panel.export_images_requested.connect(self._handle_image_export)

    def _handle_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择量热数据",
            "",
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)",
        )
        if path:
            self.current_data_path = Path(path)
            self.control_panel.update_status(f"文件就绪: {self.current_data_path.name}")
            self.control_panel.btn_calc.setEnabled(True)
            self.control_panel.btn_extract.setEnabled(True)

    def _handle_calc(self, mass: float, expected_peaks: int) -> None:
        if self.current_data_path is None:
            QMessageBox.warning(self, "缺少数据文件", "请先导入量热数据文件。")
            return

        self.control_panel.btn_calc.setEnabled(False)
        self.control_panel.btn_load.setEnabled(False)

        self.worker = KineticsWorker(self.current_data_path, mass, expected_peaks)
        self.worker.progress.connect(self.control_panel.update_status)
        self.worker.data_loaded.connect(self._on_data_loaded)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_data_loaded(self, data) -> None:
        self.cached_hydration_data = data
        self.canvas.plot_hydration_data(data.time_h, data.heat_flow_mw_g, data.cumulative_heat_j_g)

    def _on_finished(self, res) -> None:
        params, data = res
        self.cached_params = params
        self.results_panel.display_results(params)
        self.canvas.plot_hydration_data(data.time_h, data.heat_flow_mw_g, data.cumulative_heat_j_g, params=params)

        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
        self.control_panel.btn_export_excel.setEnabled(True)
        self.control_panel.btn_export_images.setEnabled(True)
        self.control_panel.update_status("解析完成。可以提取数据或导出图表。")

    def _on_error(self, err_msg: str) -> None:
        self.control_panel.update_status("核心引擎执行异常", is_error=True)
        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
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

            self.control_panel.update_status("已生成数据报表与 Origin 绘图源数据。")
            self._open_system_folder(save_path)

        except Exception as e:
            QMessageBox.critical(self, "报表生成失败", f"Excel 写入失败:\n{str(e)}")

    def _write_kinetics_tables(self, writer: pd.ExcelWriter) -> None:
        p = self.cached_params
        mix_name = self.current_data_path.stem if self.current_data_path else "Sample"

        x_k_fit = p.origin_knudsen.get("X_Fit: 1/(t-t0) [h^-1]", np.array([]))
        y_k_fit = p.origin_knudsen.get("Y_Fit: 1/Q [J^-1*g]", np.array([]))
        valid_mask = ~np.isnan(x_k_fit) & ~np.isnan(y_k_fit)
        x_k_fit, y_k_fit = x_k_fit[valid_mask], y_k_fit[valid_mask]

        r2_knudsen = "-"
        if len(x_k_fit) > 2:
            corr = np.corrcoef(x_k_fit, y_k_fit)[0, 1]
            if not np.isnan(corr):
                r2_knudsen = round(corr**2, 5)

        knudsen_eq = f"1/Q={1 / p.qmax_j_g:.5f}+{p.t50_h / p.qmax_j_g:.5f}/(t-t0)"
        pd.DataFrame(
            [
                {
                    "Mixture": mix_name,
                    "Qmax/(J·g-1)": round(p.qmax_j_g, 2),
                    "t50/h": round(p.t50_h, 2),
                    "1/Q=1/Qmax+t50/Qmax(t-t0)": knudsen_eq,
                    "R2": r2_knudsen,
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
                    "F_I equation": eq_i,
                    "R2 (I)": round(p.r2_i, 4),
                    "F_D equation": eq_d,
                    "R2 (D)": round(p.r2_d, 4),
                }
            ]
        ).to_excel(writer, sheet_name="Tab6_KD_Eqs", index=False)

        pd.DataFrame(
            [
                {
                    "Mixture": mix_name,
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
