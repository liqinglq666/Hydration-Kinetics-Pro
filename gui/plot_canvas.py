from pathlib import Path

import matplotlib

matplotlib.use('QtAgg')  # 强制使用 Qt 后端，防止主线程阻塞
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator
from matplotlib.transforms import Bbox
import matplotlib.pyplot as plt
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout
from core.data_models import KineticsParameters

# 全局注入顶刊级学术字体 (Times New Roman & STIX Math Font)
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['axes.unicode_minus'] = False


class ScientificCanvas(QWidget):
    """
    顶刊级科学绘图画布组件 (2x2 全局仪表盘)。
    集成了 Matplotlib 的 Qt 后端，提供高分辨率交互式四通道图表监控。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.fig = Figure(figsize=(12.5, 8.2), dpi=120)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # 跟踪寄生双 Y 轴，用于垃圾回收防止重影
        self.ax_raw_twin = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.axes = self.fig.subplots(2, 2)
        self._apply_dashboard_spacing()

    def _apply_dashboard_spacing(self):
        """Use explicit spacing instead of oversized tight_layout padding for a denser dashboard."""
        self.fig.subplots_adjust(left=0.075, right=0.94, bottom=0.075, top=0.925, wspace=0.42, hspace=0.42)

    def _setup_axes(self):
        """统一刷涂顶刊级别的边框与刻度美学规范，并执行画布垃圾回收"""

        if hasattr(self, 'ax_raw_twin') and self.ax_raw_twin is not None:
            self.ax_raw_twin.remove()
            self.ax_raw_twin = None

        for row in self.axes:
            for ax in row:
                ax.clear()
                ax.xaxis.set_minor_locator(AutoMinorLocator())
                ax.yaxis.set_minor_locator(AutoMinorLocator())
                ax.tick_params(which='major', width=1.4, length=5, labelsize=11)
                ax.tick_params(which='minor', width=0.9, length=3)
                for spine in ax.spines.values():
                    spine.set_linewidth(1.4)

    def plot_hydration_data(self, time_h: np.ndarray, heat_flow: np.ndarray, cumulative_heat: np.ndarray,
                            params: KineticsParameters = None):
        """
        主渲染管线入口。由 MainWindow 在数据解算完成后调用。
        """
        self._setup_axes()
        ax_raw = self.axes[0, 0]
        ax_knudsen = self.axes[0, 1]
        ax_linear = self.axes[1, 0]
        ax_env = self.axes[1, 1]

        ax_raw.set_title("1. Calorimetry Raw Data", fontweight='bold', fontsize=13, pad=8)
        line1 = ax_raw.plot(time_h, heat_flow, 'k-', linewidth=2.0, label='Heat Flow (mW/g)')
        ax_raw.set_xlabel('Time (h)', fontweight='bold', fontsize=12)
        ax_raw.set_ylabel('Heat Flow (mW/g)', fontweight='bold', fontsize=12)

        valid_idx = time_h > 0.5
        if np.any(valid_idx):
            max_hf = np.max(heat_flow[valid_idx])
            min_hf = np.min(heat_flow[valid_idx])
            ax_raw.set_ylim(min_hf - 0.1 * max_hf, max_hf * 1.2)

        self.ax_raw_twin = ax_raw.twinx()
        line2 = self.ax_raw_twin.plot(time_h, cumulative_heat, 'r-', linewidth=2.0, label='Cumulative Heat (J/g)')
        self.ax_raw_twin.set_ylabel('Cumulative Heat (J/g)', color='red', fontweight='bold', fontsize=12)
        self.ax_raw_twin.tick_params(axis='y', colors='red', which='both', labelsize=11)
        self.ax_raw_twin.spines['right'].set_color('red')
        self.ax_raw_twin.spines['right'].set_linewidth(1.4)
        self.ax_raw_twin.set_ylim(0, np.max(cumulative_heat) * 1.1)

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax_raw.legend(lines, labels, loc='center right', frameon=True, edgecolor='black', fontsize=10)

        if params is None:
            for ax in [ax_knudsen, ax_linear, ax_env]:
                ax.text(0.5, 0.5, "Awaiting Calculation...", ha='center', va='center', fontsize=13, color='gray')
            self._apply_dashboard_spacing()
            self.canvas.draw()
            return

        ax_knudsen.set_title("2. Knudsen Extrapolation ($Q_{max}$)", fontweight='bold', fontsize=13, pad=8)
        if params.origin_knudsen:
            x_all = params.origin_knudsen.get('X_All: 1/(t-t0) [h^-1]', [])
            y_all = params.origin_knudsen.get('Y_All: 1/Q [J^-1*g]', [])
            x_fit = params.origin_knudsen.get('X_Fit: 1/(t-t0) [h^-1]', [])
            y_fit = params.origin_knudsen.get('Y_Fit: 1/Q [J^-1*g]', [])

            ax_knudsen.scatter(x_all, y_all, color='gray', s=12, alpha=0.5, label='Raw Data')
            valid_mask = ~np.isnan(x_fit) & ~np.isnan(y_fit)

            r2_knudsen_str = ""
            if np.sum(valid_mask) > 2:
                corr = np.corrcoef(x_fit[valid_mask], y_fit[valid_mask])[0, 1]
                if not np.isnan(corr):
                    r2_knudsen_str = fr" ($R^2={corr ** 2:.4f}$)"

            if np.sum(valid_mask) > 0:
                ax_knudsen.plot(x_fit[valid_mask], y_fit[valid_mask], 'r-', linewidth=2.4,
                                label=fr'Linear Fit{r2_knudsen_str}')

            ax_knudsen.set_xlabel(r'$1/(t-t_0)\ [h^{-1}]$', fontweight='bold', fontsize=12)
            ax_knudsen.set_ylabel(r'$1/Q\ [J^{-1}\cdot g]$', fontweight='bold', fontsize=12)
            ax_knudsen.legend(loc='best', frameon=True, edgecolor='black', fontsize=10)

        ax_linear.set_title("3. Integral-Domain Regressions", fontweight='bold', fontsize=13, pad=8)
        if params.origin_kd_linear:
            d_lin = params.origin_kd_linear

            x_ng, y_ng = d_lin.get('[NG] X: ln(t-t0)', []), d_lin.get('[NG] Y: ln(-ln(1-α))', [])
            if len(x_ng) > 0:
                ax_linear.scatter(x_ng, y_ng, s=15, color='limegreen', alpha=0.7,
                                  label=fr'NG Data ($R^2={params.r2_ng:.4f}$)', zorder=2)
                y_ng_pred = params.n * x_ng + params.n * np.log(params.k1)
                ax_linear.plot(x_ng, y_ng_pred, color='darkgreen', linewidth=1.5, linestyle='-', zorder=3)

            x_i, y_i = d_lin.get('[I] X: ln(t-t0)', []), d_lin.get('[I] Y: ln(1-(1-α)^1/3)', [])
            if len(x_i) > 0:
                ax_linear.scatter(x_i, y_i, s=15, color='red', alpha=0.7,
                                  label=fr'I Data ($R^2={params.r2_i:.4f}$)', zorder=2)
                y_i_pred = x_i + np.log(params.k2)
                ax_linear.plot(x_i, y_i_pred, color='darkred', linewidth=1.5, linestyle='-', zorder=3)

            x_d, y_d = d_lin.get('[D] X: ln(t-t0)', []), d_lin.get('[D] Y: 2*ln(1-(1-α)^1/3)', [])
            if len(x_d) > 0:
                ax_linear.scatter(x_d, y_d, s=15, color='blue', alpha=0.7,
                                  label=fr'D Data ($R^2={params.r2_d:.4f}$)', zorder=2)
                y_d_pred = x_d + np.log(params.k3)
                ax_linear.plot(x_d, y_d_pred, color='darkblue', linewidth=1.5, linestyle='-', zorder=3)

            ax_linear.set_xlabel(r'$\ln(t-t_0)$', fontweight='bold', fontsize=12)
            ax_linear.set_ylabel(r'Kinetic Functions', fontweight='bold', fontsize=12)
            ax_linear.legend(loc='best', frameon=True, edgecolor='black', fontsize=10)

        ax_env.set_title("4. Kinetics Mechanism Envelope", fontweight='bold', fontsize=13, pad=8)
        self._plot_top_tier_envelope(ax_env, params)

        self._apply_dashboard_spacing()
        self.canvas.draw()

    def _plot_top_tier_envelope(self, ax, params: KineticsParameters):
        """核心物理包络线渲染引擎 (UI 美学优化版)"""
        alpha_exp = params.origin_rates['X: Alpha (水化度)']
        rate_exp = params.origin_rates['Y1: Exp_Rate [h^-1]']
        f_ng = params.origin_rates['Y2: F_NG [h^-1]']
        f_i = params.origin_rates['Y3: F_I [h^-1]']
        f_d = params.origin_rates['Y4: F_D [h^-1]']

        ax.plot(alpha_exp, rate_exp, color='black', linestyle='-', linewidth=2.4, label=r'$d\alpha/dt$', zorder=4)
        ax.plot(alpha_exp, f_ng, color='limegreen', linestyle='-.', linewidth=1.8, label=r'$F_{NG}(\alpha)$', zorder=3)
        ax.plot(alpha_exp, f_i, color='red', linestyle='--', linewidth=1.8, label=r'$F_I(\alpha)$', zorder=3)
        ax.plot(alpha_exp, f_d, color='blue', linestyle=':', linewidth=2.0, label=r'$F_D(\alpha)$', zorder=3)

        y_max = np.max(rate_exp) * 1.35 if len(rate_exp) > 0 else 0.1

        ax.axvline(x=params.alpha_1, color='gray', linestyle='--', linewidth=1.0, alpha=0.6)
        ax.text(params.alpha_1 + 0.015, y_max * 0.08, fr'$\alpha_1$={params.alpha_1:.4f}',
                fontsize=10, fontfamily='Times New Roman', color='#333333')

        ax.axvline(x=params.alpha_2, color='gray', linestyle='--', linewidth=1.0, alpha=0.6)
        ax.text(params.alpha_2 + 0.015, y_max * 0.08, fr'$\alpha_2$={params.alpha_2:.4f}',
                fontsize=10, fontfamily='Times New Roman', color='#333333')

        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, y_max)
        ax.set_xlabel(r'$\alpha$', fontsize=12, fontweight='bold')
        ax.set_ylabel(r'$d\alpha/dt\ [h^{-1}]$', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', frameon=False, fontsize=10)

    def _save_cropped_axis(self, ax, output_path: Path, extra_axes=None, dpi: int = 600) -> None:
        """Save one subplot as a publication-style cropped image from the dashboard figure."""
        self.canvas.draw()
        renderer = self.canvas.get_renderer()
        axes = [ax] + list(extra_axes or [])
        bboxes = [item.get_tightbbox(renderer) for item in axes if item is not None]
        bbox = Bbox.union(bboxes).expanded(1.08, 1.12)
        bbox_inches = bbox.transformed(self.fig.dpi_scale_trans.inverted())
        self.fig.savefig(output_path, dpi=dpi, bbox_inches=bbox_inches, facecolor='white')

    def save_individual_plots(self, dir_path: str):
        """
        导出高清学术图谱。

        输出内容：
        1. 2x2 dashboard 总图；
        2. 四张独立 cropped subplot，便于直接放入论文、PPT 或 Origin 对照排版。
        """
        try:
            out_dir = Path(dir_path)
            out_dir.mkdir(parents=True, exist_ok=True)

            self.fig.savefig(out_dir / 'Kinetics_Dashboard_HighRes.png', dpi=600, bbox_inches='tight', facecolor='white')
            self._save_cropped_axis(
                self.axes[0, 0],
                out_dir / 'Fig1_Calorimetry_Raw_Data.png',
                extra_axes=[self.ax_raw_twin],
                dpi=600,
            )
            self._save_cropped_axis(self.axes[0, 1], out_dir / 'Fig2_Knudsen_Extrapolation.png', dpi=600)
            self._save_cropped_axis(self.axes[1, 0], out_dir / 'Fig3_KD_Integral_Domain_Regressions.png', dpi=600)
            self._save_cropped_axis(self.axes[1, 1], out_dir / 'Fig4_Kinetics_Mechanism_Envelope.png', dpi=600)
        except Exception as e:
            raise RuntimeError(f"图像渲染流写入失败: {str(e)}")
