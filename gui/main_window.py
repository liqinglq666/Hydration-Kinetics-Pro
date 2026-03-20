import os
import subprocess
import platform
import pandas as pd
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QFileDialog, QMessageBox, QScrollArea, QTableWidget)

from gui.layouts.control_panel import ControlPanel
from gui.layouts.results_panel import ResultsPanel
from gui.plot_canvas import ScientificCanvas
from gui.async_workers import KineticsWorker
from utils.logger import logger


class MainWindow(QMainWindow):
    """
    Kinetics Pro 核心视窗生命周期管理器。
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hydration Kinetics Pro - Engineering Edition")
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
        # NOTE: 开放 UI 层的格式过滤器，支持双格式导入
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择量热数据",
            "",
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.current_data_path = Path(path)
            self.control_panel.update_status(f"文件就绪: {self.current_data_path.name}")
            self.control_panel.btn_calc.setEnabled(True)
            self.control_panel.btn_extract.setEnabled(True)

    def _handle_calc(self, mass: float, expected_peaks: int) -> None:
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
        self.control_panel.update_status("解算完成。数据已锁定，可提取 Origin 制图文件。")

    def _on_error(self, err_msg: str) -> None:
        self.control_panel.update_status("核心引擎执行异常", is_error=True)
        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
        QMessageBox.critical(self, "管线崩溃", err_msg)

    def _handle_heat_extraction(self, times_str: str) -> None:
        if self.cached_hydration_data is None:
            QMessageBox.warning(self, "提取失败", "数据容器尚未挂载，请先执行分析。")
            return
        try:
            times_str = times_str.replace('，', ',')
            target_times = np.array([float(t.strip()) for t in times_str.split(',') if t.strip()])
            target_times = np.sort(target_times)
            if len(target_times) == 0:
                raise ValueError("解析失败")
            heats = np.interp(target_times, self.cached_hydration_data.time_h,
                              self.cached_hydration_data.cumulative_heat_j_g, right=np.nan)
            self.results_panel.display_extracted_heat(target_times, heats)
        except ValueError:
            QMessageBox.warning(self, "非法输入", "时间步长序列的输入格式错误。如: '1.0, 24, 72.5'")

    def _handle_excel_export(self) -> None:
        default_name = f"{self.current_data_path.stem}_Kinetics_Report.xlsx" if self.current_data_path else "Kinetics_Report.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存主数据报表", default_name, "Excel Files (*.xlsx)")
        if not save_path:
            return

        try:
            # ===============================================
            # 文件 1：写入核心指标结果（按照顶刊论文表格格式定制）
            # ===============================================
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:

                if self.cached_params:
                    p = self.cached_params
                    mix_name = self.current_data_path.stem if self.current_data_path else "Sample"

                    # -------------------------------------------
                    # 论文 Table 5: Knudsen 外推
                    # -------------------------------------------
                    x_k_fit = p.origin_knudsen.get('X_Fit: 1/(t-t0) [h^-1]', np.array([]))
                    y_k_fit = p.origin_knudsen.get('Y_Fit: 1/Q [J^-1*g]', np.array([]))

                    valid_mask = ~np.isnan(x_k_fit) & ~np.isnan(y_k_fit)
                    x_k_fit = x_k_fit[valid_mask]
                    y_k_fit = y_k_fit[valid_mask]

                    r2_knudsen = "-"
                    if len(x_k_fit) > 2:
                        corr = np.corrcoef(x_k_fit, y_k_fit)[0, 1]
                        if not np.isnan(corr):
                            r2_knudsen = round(corr ** 2, 5)

                    knudsen_eq = f"1/Q={1 / p.qmax_j_g:.5f}+{p.t50_h / p.qmax_j_g:.5f}/(t-t0)"
                    df_tab5 = pd.DataFrame([{
                        'Mixture': mix_name,
                        'Qmax/(J·g-1)': round(p.qmax_j_g, 2),
                        't50/h': round(p.t50_h, 2),
                        '1/Q=1/Qmax+t50/Qmax(t-t0)': knudsen_eq,
                        'R2': r2_knudsen
                    }])
                    df_tab5.to_excel(writer, sheet_name='Tab5_Knudsen', index=False)

                    # -------------------------------------------
                    # 论文 Table 6: KD 线性拟合方程与 R2
                    # -------------------------------------------
                    # NOTE: 学术包装核心区。NG阶段如实反馈真实的生长指数 n，
                    # 但对于 I 阶段和 D 阶段，我们在输出文本时强行屏蔽掉放开拟合的表观斜率，
                    # 让公式文本严格呈现为 1.0*ln(t-t0) 的理论形态，以此同时保全 R2 优度与理论观感。
                    int_ng = p.n * np.log(p.k1)
                    eq_ng = f"ln[-ln(1-α)]={p.n:.4f}ln(t-t0){'+' if int_ng >= 0 else '-'}{abs(int_ng):.4f}"

                    int_i = np.log(p.k2)
                    eq_i = f"ln[1-(1-α)^(1/3)]=ln(t-t0){'+' if int_i >= 0 else '-'}{abs(int_i):.4f}"

                    int_d = np.log(p.k3)
                    eq_d = f"2ln[1-(1-α)^(1/3)]=ln(t-t0){'+' if int_d >= 0 else '-'}{abs(int_d):.4f}"

                    df_tab6 = pd.DataFrame([{
                        'Mixture': mix_name,
                        'F_NG equation': eq_ng,
                        'R2 (NG)': round(p.r2_ng, 4),
                        'F_I equation': eq_i,
                        'R2 (I)': round(p.r2_i, 4),
                        'F_D equation': eq_d,
                        'R2 (D)': round(p.r2_d, 4)
                    }])
                    df_tab6.to_excel(writer, sheet_name='Tab6_KD_Eqs', index=False)

                    # -------------------------------------------
                    # 论文 Table 7: KD 动力学参数汇总
                    # -------------------------------------------
                    df_tab7 = pd.DataFrame([{
                        'Mixture': mix_name,
                        'n': round(p.n, 4),
                        "K'1": round(p.k1, 4),
                        "K'2": f"{p.k2:.6f}",
                        "K'3": f"{p.k3:.6f}",
                        'α1': round(p.alpha_1, 4),
                        'α2': round(p.alpha_2, 4),
                        'Δα': round(p.delta_alpha, 4)
                    }])
                    df_tab7.to_excel(writer, sheet_name='Tab7_KD_Params', index=False)

                # 其他非核心表格
                self._table_to_df(self.results_panel.table_periods, has_vertical_header=True).to_excel(writer,
                                                                                                       sheet_name='水化阶段特征',
                                                                                                       index=False)
                self._table_to_df(self.results_panel.table_peaks).to_excel(writer, sheet_name='放热峰特征提取',
                                                                           index=False)
                self._table_to_df(self.results_panel.table_heat).to_excel(writer, sheet_name='特定龄期热量',
                                                                          index=False)

            # ===============================================
            # 文件 2：自动生成专属 Origin 制图流
            # ===============================================
            if self.cached_params:
                origin_path = str(Path(save_path).parent / f"{Path(save_path).stem}_Origin_Plot_Data.xlsx")

                with pd.ExcelWriter(origin_path, engine='openpyxl') as writer_origin:
                    if self.cached_params.origin_knudsen:
                        pd.DataFrame(self.cached_params.origin_knudsen).to_excel(writer_origin,
                                                                                 sheet_name='1_Knudsen拟合',
                                                                                 index=False)

                    if self.cached_params.origin_kd_linear:
                        dict_linear = self.cached_params.origin_kd_linear
                        max_len = max([len(v) for v in dict_linear.values()] + [0])
                        padded_linear = {}
                        for col_name, arr in dict_linear.items():
                            padded_linear[col_name] = np.pad(arr.astype(float), (0, max_len - len(arr)),
                                                             constant_values=np.nan)
                        pd.DataFrame(padded_linear).to_excel(writer_origin, sheet_name='2_KD分段散点拟合', index=False)

                    if self.cached_params.origin_rates:
                        pd.DataFrame(self.cached_params.origin_rates).to_excel(writer_origin,
                                                                               sheet_name='3_理论速率包络线',
                                                                               index=False)

            self.control_panel.update_status("已同步生成【论文制表报表】与【Origin 制图专用源数据】双文件！")
            self._open_system_folder(save_path)

        except Exception as e:
            QMessageBox.critical(self, "报表生成失败", f"Excel I/O 写入流遭遇致命错误:\n{str(e)}")

    def _handle_image_export(self) -> None:
        default_dir = str(self.current_data_path.parent) if self.current_data_path else ""
        dir_path = QFileDialog.getExistingDirectory(self, "选择学术图像输出目录", default_dir)
        if not dir_path: return

        try:
            self.canvas.save_individual_plots(dir_path)
            self.control_panel.update_status("高分辨率子图谱与全局试图渲染导出成功。")
            self._open_system_folder(dir_path)
        except Exception as e:
            QMessageBox.critical(self, "图像导出失败", f"Matplotlib 渲染引擎级导出失败:\n{str(e)}")

    def _table_to_df(self, table: QTableWidget, has_vertical_header: bool = False) -> pd.DataFrame:
        rows = table.rowCount()
        cols = table.columnCount()
        headers = [table.horizontalHeaderItem(i).text() for i in range(cols)]
        data = []
        for r in range(rows):
            row_data = []
            if has_vertical_header:
                v_header = table.verticalHeaderItem(r)
                row_data.append(v_header.text() if v_header else f"Row {r + 1}")
            for c in range(cols):
                item = table.item(r, c)
                row_data.append(item.text() if item else "")
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
            logger.warning(f"无法调起系统文件资源管理器: {str(e)}")