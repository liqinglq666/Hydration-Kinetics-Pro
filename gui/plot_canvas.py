from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator
import matplotlib.pyplot as plt
import numpy as np

from PySide6.QtWidgets import QVBoxLayout, QWidget
from core.data_models import KineticsParameters

plt.rcParams["mathtext.fontset"] = "stix"
plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["axes.unicode_minus"] = False


class ScientificCanvas(QWidget):
    """科研绘图画布。

    GUI 中默认一次只显示一个图表卡片；导出时仍可自动生成 dashboard 和四张独立图。
    """

    MODE_TITLES = {
        "raw": "1. Calorimetry Raw Data",
        "knudsen": "2. Knudsen Extrapolation ($Q_{max}$)",
        "linear": "3. Integral-Domain Regressions",
        "envelope": "4. Kinetics Mechanism Envelope",
        "dashboard": "Hydration Kinetics Dashboard",
    }

    def __init__(self, parent=None, plot_mode: str = "raw"):
        super().__init__(parent)
        self.plot_mode = plot_mode
        self.fig = Figure(figsize=(10.8, 5.6), dpi=120)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.ax_raw_twin = None
        self._last_time_h = None
        self._last_heat_flow = None
        self._last_cumulative_heat = None
        self._last_params = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._render_empty("请先导入数据并执行分析")

    def set_plot_mode(self, mode: str) -> None:
        if mode not in {"raw", "knudsen", "linear", "envelope", "dashboard"}:
            return
        self.plot_mode = mode
        self._render()

    def plot_hydration_data(
        self,
        time_h: np.ndarray,
        heat_flow: np.ndarray,
        cumulative_heat: np.ndarray,
        params: KineticsParameters = None,
    ):
        self._last_time_h = np.asarray(time_h, dtype=float)
        self._last_heat_flow = np.asarray(heat_flow, dtype=float)
        self._last_cumulative_heat = np.asarray(cumulative_heat, dtype=float)
        self._last_params = params
        self._render()

    def _clear_figure(self) -> None:
        self.ax_raw_twin = None
        self.fig.clear()

    def _style_axis(self, ax) -> None:
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.tick_params(which="major", width=1.4, length=5, labelsize=11)
        ax.tick_params(which="minor", width=0.9, length=3)
        for spine in ax.spines.values():
            spine.set_linewidth(1.4)

    def _render_empty(self, message: str) -> None:
        self._clear_figure()
        ax = self.fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=14, color="#6b7280")
        ax.set_axis_off()
        self.fig.subplots_adjust(left=0.06, right=0.96, bottom=0.08, top=0.94)
        self.canvas.draw()

    def _render(self) -> None:
        if self._last_time_h is None:
            self._render_empty("请先导入数据并执行分析")
            return

        if self.plot_mode == "dashboard":
            self._render_dashboard()
            return

        self._clear_figure()
        ax = self.fig.add_subplot(111)
        self._style_axis(ax)

        if self.plot_mode == "raw":
            self._plot_raw(ax, self._last_time_h, self._last_heat_flow, self._last_cumulative_heat)
        elif self._last_params is None:
            self._plot_waiting(ax, "等待动力学计算完成...")
        elif self.plot_mode == "knudsen":
            self._plot_knudsen(ax, self._last_params)
        elif self.plot_mode == "linear":
            self._plot_linear(ax, self._last_params)
        elif self.plot_mode == "envelope":
            self._plot_envelope(ax, self._last_params)

        self.fig.subplots_adjust(left=0.095, right=0.92, bottom=0.14, top=0.88)
        self.canvas.draw()

    def _render_dashboard(self) -> None:
        self._clear_figure()
        axes = self.fig.subplots(2, 2)
        for row in axes:
            for ax in row:
                self._style_axis(ax)

        self._plot_raw(axes[0, 0], self._last_time_h, self._last_heat_flow, self._last_cumulative_heat)
        if self._last_params is None:
            for ax in [axes[0, 1], axes[1, 0], axes[1, 1]]:
                self._plot_waiting(ax, "Awaiting Calculation...")
        else:
            self._plot_knudsen(axes[0, 1], self._last_params)
            self._plot_linear(axes[1, 0], self._last_params)
            self._plot_envelope(axes[1, 1], self._last_params)

        self.fig.subplots_adjust(left=0.075, right=0.94, bottom=0.075, top=0.925, wspace=0.42, hspace=0.42)
        self.canvas.draw()

    def _plot_waiting(self, ax, message: str) -> None:
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=13, color="#6b7280")
        ax.set_axis_off()

    def _plot_raw(self, ax, time_h: np.ndarray, heat_flow: np.ndarray, cumulative_heat: np.ndarray) -> None:
        ax.set_title(self.MODE_TITLES["raw"], fontweight="bold", fontsize=14, pad=10)
        line1 = ax.plot(time_h, heat_flow, "k-", linewidth=2.2, label="Heat Flow (mW/g)")
        ax.set_xlabel("Time (h)", fontweight="bold", fontsize=12)
        ax.set_ylabel("Heat Flow (mW/g)", fontweight="bold", fontsize=12)

        valid_idx = time_h > 0.5
        if np.any(valid_idx):
            max_hf = float(np.max(heat_flow[valid_idx]))
            min_hf = float(np.min(heat_flow[valid_idx]))
            ax.set_ylim(min_hf - 0.1 * max_hf, max_hf * 1.2)

        self.ax_raw_twin = ax.twinx()
        line2 = self.ax_raw_twin.plot(time_h, cumulative_heat, "r-", linewidth=2.2, label="Cumulative Heat (J/g)")
        self.ax_raw_twin.set_ylabel("Cumulative Heat (J/g)", color="red", fontweight="bold", fontsize=12)
        self.ax_raw_twin.tick_params(axis="y", colors="red", which="both", labelsize=11)
        self.ax_raw_twin.spines["right"].set_color("red")
        self.ax_raw_twin.spines["right"].set_linewidth(1.4)
        if np.max(cumulative_heat) > 0:
            self.ax_raw_twin.set_ylim(0, np.max(cumulative_heat) * 1.1)

        lines = line1 + line2
        labels = [line.get_label() for line in lines]
        ax.legend(lines, labels, loc="center right", frameon=True, edgecolor="black", fontsize=10)

    def _plot_knudsen(self, ax, params: KineticsParameters) -> None:
        ax.set_title(self.MODE_TITLES["knudsen"], fontweight="bold", fontsize=14, pad=10)
        if not params.origin_knudsen:
            self._plot_waiting(ax, "无 Knudsen 绘图数据")
            return

        x_all = params.origin_knudsen.get("X_All: 1/(t-t0) [h^-1]", [])
        y_all = params.origin_knudsen.get("Y_All: 1/Q [J^-1*g]", [])
        x_fit = params.origin_knudsen.get("X_Fit: 1/(t-t0) [h^-1]", [])
        y_fit = params.origin_knudsen.get("Y_Fit: 1/Q [J^-1*g]", [])

        ax.scatter(x_all, y_all, color="gray", s=16, alpha=0.55, label="Raw Data")
        valid_mask = ~np.isnan(x_fit) & ~np.isnan(y_fit)
        r2_text = ""
        if np.sum(valid_mask) > 2:
            corr = np.corrcoef(x_fit[valid_mask], y_fit[valid_mask])[0, 1]
            if not np.isnan(corr):
                r2_text = fr" ($R^2={corr ** 2:.4f}$)"
        if np.sum(valid_mask) > 0:
            ax.plot(x_fit[valid_mask], y_fit[valid_mask], "r-", linewidth=2.6, label=fr"Linear Fit{r2_text}")

        ax.set_xlabel(r"$1/(t-t_0)\ [h^{-1}]$", fontweight="bold", fontsize=12)
        ax.set_ylabel(r"$1/Q\ [J^{-1}\cdot g]$", fontweight="bold", fontsize=12)
        ax.legend(loc="best", frameon=True, edgecolor="black", fontsize=10)

    def _plot_linear(self, ax, params: KineticsParameters) -> None:
        ax.set_title(self.MODE_TITLES["linear"], fontweight="bold", fontsize=14, pad=10)
        if not params.origin_kd_linear:
            self._plot_waiting(ax, "无 K-D 分段拟合数据")
            return

        d_lin = params.origin_kd_linear
        x_ng, y_ng = d_lin.get("[NG] X: ln(t-t0)", []), d_lin.get("[NG] Y: ln(-ln(1-α))", [])
        if len(x_ng) > 0:
            ax.scatter(x_ng, y_ng, s=18, color="limegreen", alpha=0.72, label=fr"NG Data ($R^2={params.r2_ng:.4f}$)", zorder=2)
            ax.plot(x_ng, params.n * x_ng + params.n * np.log(params.k1), color="darkgreen", linewidth=1.8, zorder=3)

        x_i, y_i = d_lin.get("[I] X: ln(t-t0)", []), d_lin.get("[I] Y: ln(1-(1-α)^1/3)", [])
        if len(x_i) > 0:
            ax.scatter(x_i, y_i, s=18, color="red", alpha=0.72, label=fr"I Data ($R^2={params.r2_i:.4f}$)", zorder=2)
            ax.plot(x_i, x_i + np.log(params.k2), color="darkred", linewidth=1.8, zorder=3)

        x_d, y_d = d_lin.get("[D] X: ln(t-t0)", []), d_lin.get("[D] Y: 2*ln(1-(1-α)^1/3)", [])
        if len(x_d) > 0:
            ax.scatter(x_d, y_d, s=18, color="blue", alpha=0.72, label=fr"D Data ($R^2={params.r2_d:.4f}$)", zorder=2)
            ax.plot(x_d, x_d + np.log(params.k3), color="darkblue", linewidth=1.8, zorder=3)

        ax.set_xlabel(r"$\ln(t-t_0)$", fontweight="bold", fontsize=12)
        ax.set_ylabel("Kinetic Functions", fontweight="bold", fontsize=12)
        ax.legend(loc="best", frameon=True, edgecolor="black", fontsize=10)

    def _plot_envelope(self, ax, params: KineticsParameters) -> None:
        ax.set_title(self.MODE_TITLES["envelope"], fontweight="bold", fontsize=14, pad=10)
        if not params.origin_rates:
            self._plot_waiting(ax, "无机制包络线数据")
            return

        alpha_exp = params.origin_rates["X: Alpha (水化度)"]
        rate_exp = params.origin_rates["Y1: Exp_Rate [h^-1]"]
        f_ng = params.origin_rates["Y2: F_NG [h^-1]"]
        f_i = params.origin_rates["Y3: F_I [h^-1]"]
        f_d = params.origin_rates["Y4: F_D [h^-1]"]

        ax.plot(alpha_exp, rate_exp, color="black", linestyle="-", linewidth=2.6, label=r"$d\alpha/dt$", zorder=4)
        ax.plot(alpha_exp, f_ng, color="limegreen", linestyle="-.", linewidth=2.0, label=r"$F_{NG}(\alpha)$", zorder=3)
        ax.plot(alpha_exp, f_i, color="red", linestyle="--", linewidth=2.0, label=r"$F_I(\alpha)$", zorder=3)
        ax.plot(alpha_exp, f_d, color="blue", linestyle=":", linewidth=2.2, label=r"$F_D(\alpha)$", zorder=3)

        y_max = np.max(rate_exp) * 1.35 if len(rate_exp) > 0 else 0.1
        ax.axvline(x=params.alpha_1, color="gray", linestyle="--", linewidth=1.1, alpha=0.65)
        ax.text(params.alpha_1 + 0.015, y_max * 0.08, fr"$\alpha_1$={params.alpha_1:.4f}", fontsize=10, color="#333333")
        ax.axvline(x=params.alpha_2, color="gray", linestyle="--", linewidth=1.1, alpha=0.65)
        ax.text(params.alpha_2 + 0.015, y_max * 0.08, fr"$\alpha_2$={params.alpha_2:.4f}", fontsize=10, color="#333333")

        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, y_max)
        ax.set_xlabel(r"$\alpha$", fontsize=12, fontweight="bold")
        ax.set_ylabel(r"$d\alpha/dt\ [h^{-1}]$", fontsize=12, fontweight="bold")
        ax.legend(loc="upper right", frameon=False, fontsize=10)

    def save_individual_plots(self, dir_path: str):
        """导出 dashboard 总图和四张独立高清图。"""
        if self._last_time_h is None:
            raise RuntimeError("没有可导出的图像，请先导入并分析数据。")

        try:
            out_dir = Path(dir_path)
            out_dir.mkdir(parents=True, exist_ok=True)

            original_mode = self.plot_mode
            export_map = {
                "dashboard": "Kinetics_Dashboard_HighRes.png",
                "raw": "Fig1_Calorimetry_Raw_Data.png",
                "knudsen": "Fig2_Knudsen_Extrapolation.png",
                "linear": "Fig3_KD_Integral_Domain_Regressions.png",
                "envelope": "Fig4_Kinetics_Mechanism_Envelope.png",
            }
            for mode, filename in export_map.items():
                self.plot_mode = mode
                self._render()
                self.fig.savefig(out_dir / filename, dpi=600, bbox_inches="tight", facecolor="white")

            self.plot_mode = original_mode
            self._render()
        except Exception as e:
            raise RuntimeError(f"图像渲染流写入失败: {str(e)}")
