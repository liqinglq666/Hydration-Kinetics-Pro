import matplotlib

matplotlib.use('QtAgg')  # 强制使用 Qt 后端，防止主线程阻塞
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator
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

        # 初始化大尺寸图形对象与 Qt 画布 (适配 2x2 布局)
        self.fig = Figure(figsize=(14, 10), dpi=120)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # 跟踪寄生双 Y 轴，用于垃圾回收防止重影
        self.ax_raw_twin = None

        # 构建局部布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # 恢复经典的 2x2 四图分布阵列
        self.axes = self.fig.subplots(2, 2)
        self.fig.tight_layout(pad=3.5)

    def _setup_axes(self):
        """统一刷涂顶刊级别的边框与刻度美学规范，并执行画布垃圾回收"""

        # 彻底销毁旧的寄生双 Y 轴，防止连续计算时红线重叠
        if hasattr(self, 'ax_raw_twin') and self.ax_raw_twin is not None:
            self.ax_raw_twin.remove()
            self.ax_raw_twin = None

        for row in self.axes:
            for ax in row:
                ax.clear()
                # 开启次级刻度线
                ax.xaxis.set_minor_locator(AutoMinorLocator())
                ax.yaxis.set_minor_locator(AutoMinorLocator())
                # 加粗主刻度与边框，提升学术硬朗感
                ax.tick_params(which='major', width=1.5, length=6, labelsize=12)
                ax.tick_params(which='minor', width=1.0, length=4)
                for spine in ax.spines.values():
                    spine.set_linewidth(1.5)

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

        # ==========================================
        # 图 1 (左上)：基础量热曲线 (双 Y 轴)
        # ==========================================
        ax_raw.set_title("1. Calorimetry Raw Data", fontweight='bold', fontsize=14, pad=10)
        line1 = ax_raw.plot(time_h, heat_flow, 'k-', linewidth=2.0, label='Heat Flow (mW/g)')
        ax_raw.set_xlabel('Time (h)', fontweight='bold', fontsize=13)
        ax_raw.set_ylabel('Heat Flow (mW/g)', fontweight='bold', fontsize=13)

        # 智能 Y 轴缩放：屏蔽前 0.5 小时的初始接触热毛刺
        valid_idx = time_h > 0.5
        if np.any(valid_idx):
            max_hf = np.max(heat_flow[valid_idx])
            min_hf = np.min(heat_flow[valid_idx])
            ax_raw.set_ylim(min_hf - 0.1 * max_hf, max_hf * 1.2)

        # 重建全新的寄生双 Y 轴并保存引用
        self.ax_raw_twin = ax_raw.twinx()
        line2 = self.ax_raw_twin.plot(time_h, cumulative_heat, 'r-', linewidth=2.0, label='Cumulative Heat (J/g)')
        self.ax_raw_twin.set_ylabel('Cumulative Heat (J/g)', color='red', fontweight='bold', fontsize=13)

        # 严格对齐刻度线颜色
        self.ax_raw_twin.tick_params(axis='y', colors='red', which='both')
        self.ax_raw_twin.spines['right'].set_color('red')
        self.ax_raw_twin.spines['right'].set_linewidth(1.5)
        self.ax_raw_twin.set_ylim(0, np.max(cumulative_heat) * 1.1)

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax_raw.legend(lines, labels, loc='center right', frameon=True, edgecolor='black', fontsize=11)

        # 如果还没有计算参数，其余三个图显示待机状态
        if params is None:
            for ax in [ax_knudsen, ax_linear, ax_env]:
                ax.text(0.5, 0.5, "Awaiting Calculation...", ha='center', va='center', fontsize=14, color='gray')
            self.fig.tight_layout(pad=3.5)
            self.canvas.draw()
            return

        # ==========================================
        # 图 2 (右上)：Knudsen 极限热量外推 (注入 R²)
        # ==========================================
        ax_knudsen.set_title("2. Knudsen Extrapolation ($Q_{max}$)", fontweight='bold', fontsize=14, pad=10)
        if params.origin_knudsen:
            x_all = params.origin_knudsen.get('X_All: 1/(t-t0) [h^-1]', [])
            y_all = params.origin_knudsen.get('Y_All: 1/Q [J^-1*g]', [])
            x_fit = params.origin_knudsen.get('X_Fit: 1/(t-t0) [h^-1]', [])
            y_fit = params.origin_knudsen.get('Y_Fit: 1/Q [J^-1*g]', [])

            ax_knudsen.scatter(x_all, y_all, color='gray', s=12, alpha=0.5, label='Raw Data')

            valid_mask = ~np.isnan(x_fit) & ~np.isnan(y_fit)

            # 动态计算并注入 Knudsen 拟合优度 R²
            r2_knudsen_str = ""
            if np.sum(valid_mask) > 2:
                corr = np.corrcoef(x_fit[valid_mask], y_fit[valid_mask])[0, 1]
                if not np.isnan(corr):
                    r2_knudsen_str = fr" ($R^2={corr ** 2:.4f}$)"

            if np.sum(valid_mask) > 0:
                ax_knudsen.plot(x_fit[valid_mask], y_fit[valid_mask], 'r-', linewidth=2.5,
                                label=fr'Linear Fit{r2_knudsen_str}')

            ax_knudsen.set_xlabel(r'$1/(t-t_0)\ [h^{-1}]$', fontweight='bold', fontsize=13)
            ax_knudsen.set_ylabel(r'$1/Q\ [J^{-1}\cdot g]$', fontweight='bold', fontsize=13)
            ax_knudsen.legend(loc='best', frameon=True, edgecolor='black', fontsize=11)

        # ==========================================
        # 图 3 (左下)：K-D 阶段散点寻优拟合 (注入 R²)
        # ==========================================
        ax_linear.set_title("3. Integral-Domain Regressions", fontweight='bold', fontsize=14, pad=10)
        if params.origin_kd_linear:
            d_lin = params.origin_kd_linear

            # NG 阶段散点与理论直线 (注入 R²)
            x_ng, y_ng = d_lin.get('[NG] X: ln(t-t0)', []), d_lin.get('[NG] Y: ln(-ln(1-α))', [])
            if len(x_ng) > 0:
                ax_linear.scatter(x_ng, y_ng, s=15, color='limegreen', alpha=0.7,
                                  label=fr'NG Data ($R^2={params.r2_ng:.4f}$)', zorder=2)
                y_ng_pred = params.n * x_ng + params.n * np.log(params.k1)
                ax_linear.plot(x_ng, y_ng_pred, color='darkgreen', linewidth=1.5, linestyle='-', zorder=3)

            # I 阶段散点与理论直线 (注入 R²)
            x_i, y_i = d_lin.get('[I] X: ln(t-t0)', []), d_lin.get('[I] Y: ln(1-(1-α)^1/3)', [])
            if len(x_i) > 0:
                ax_linear.scatter(x_i, y_i, s=15, color='red', alpha=0.7,
                                  label=fr'I Data ($R^2={params.r2_i:.4f}$)', zorder=2)
                y_i_pred = x_i + np.log(params.k2)
                ax_linear.plot(x_i, y_i_pred, color='darkred', linewidth=1.5, linestyle='-', zorder=3)

            # D 阶段散点与理论直线 (注入 R²)
            x_d, y_d = d_lin.get('[D] X: ln(t-t0)', []), d_lin.get('[D] Y: 2*ln(1-(1-α)^1/3)', [])
            if len(x_d) > 0:
                ax_linear.scatter(x_d, y_d, s=15, color='blue', alpha=0.7,
                                  label=fr'D Data ($R^2={params.r2_d:.4f}$)', zorder=2)
                y_d_pred = x_d + np.log(params.k3)
                ax_linear.plot(x_d, y_d_pred, color='darkblue', linewidth=1.5, linestyle='-', zorder=3)

            ax_linear.set_xlabel(r'$\ln(t-t_0)$', fontweight='bold', fontsize=13)
            ax_linear.set_ylabel(r'Kinetic Functions', fontweight='bold', fontsize=13)
            ax_linear.legend(loc='best', frameon=True, edgecolor='black', fontsize=11)

        # ==========================================
        # 图 4 (右下)：动力学速率包络相切线
        # ==========================================
        ax_env.set_title("4. Kinetics Mechanism Envelope", fontweight='bold', fontsize=14, pad=10)
        self._plot_top_tier_envelope(ax_env, params)

        self.fig.tight_layout(pad=3.5)
        self.canvas.draw()

    def _plot_top_tier_envelope(self, ax, params: KineticsParameters):
        """核心物理包络线渲染引擎 (UI 美学优化版)"""
        alpha_exp = params.origin_rates['X: Alpha (水化度)']
        rate_exp = params.origin_rates['Y1: Exp_Rate [h^-1]']
        f_ng = params.origin_rates['Y2: F_NG [h^-1]']
        f_i = params.origin_rates['Y3: F_I [h^-1]']
        f_d = params.origin_rates['Y4: F_D [h^-1]']

        # 优化线宽，降低虚线视觉干扰，突出黑色实验主线
        ax.plot(alpha_exp, rate_exp, color='black', linestyle='-', linewidth=2.5, label=r'$d\alpha/dt$', zorder=4)
        ax.plot(alpha_exp, f_ng, color='limegreen', linestyle='-.', linewidth=1.8, label=r'$F_{NG}(\alpha)$', zorder=3)
        ax.plot(alpha_exp, f_i, color='red', linestyle='--', linewidth=1.8, label=r'$F_I(\alpha)$', zorder=3)
        ax.plot(alpha_exp, f_d, color='blue', linestyle=':', linewidth=2.0, label=r'$F_D(\alpha)$', zorder=3)

        # 抬高 Y 轴上限，给图例和标注留出呼吸空间
        y_max = np.max(rate_exp) * 1.35 if len(rate_exp) > 0 else 0.1

        # 交点标记线优化：颜色变浅，字体移到底部防止遮挡曲线
        ax.axvline(x=params.alpha_1, color='gray', linestyle='--', linewidth=1.0, alpha=0.6)
        ax.text(params.alpha_1 + 0.015, y_max * 0.08, fr'$\alpha_1$={params.alpha_1:.4f}',
                fontsize=11, fontfamily='Times New Roman', color='#333333')

        ax.axvline(x=params.alpha_2, color='gray', linestyle='--', linewidth=1.0, alpha=0.6)
        ax.text(params.alpha_2 + 0.015, y_max * 0.08, fr'$\alpha_2$={params.alpha_2:.4f}',
                fontsize=11, fontfamily='Times New Roman', color='#333333')

        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, y_max)
        ax.set_xlabel(r'$\alpha$', fontsize=14, fontweight='bold')
        ax.set_ylabel(r'$d\alpha/dt\ [h^{-1}]$', fontsize=14, fontweight='bold')

        # 图例去背景色，避免遮盖曲线
        ax.legend(loc='upper right', frameon=False, fontsize=12)

    def save_individual_plots(self, dir_path: str):
        """
        导出高清学术图谱引擎。
        """
        import os
        from pathlib import Path
        try:
            out_dir = Path(dir_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            self.fig.savefig(out_dir / 'Kinetics_Dashboard_HighRes.png', dpi=400, bbox_inches='tight')
        except Exception as e:
            raise RuntimeError(f"图像渲染流写入失败: {str(e)}")