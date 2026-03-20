import numpy as np
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.data_models import KineticsParameters


class ScientificCanvas(FigureCanvas):
    """
    科研级图表渲染画布。
    负责将水化动力学数据映射为四宫格 SCI 出版标准图像。
    """

    def __init__(self, parent=None) -> None:
        self.fig = Figure(figsize=(12, 10), dpi=100)
        self.ax_tl = self.fig.add_subplot(221)
        self.ax_tl_twin = self.ax_tl.twinx()
        self.ax_tr = self.fig.add_subplot(222)
        self.ax_bl = self.fig.add_subplot(223)
        self.ax_br = self.fig.add_subplot(224)
        super().__init__(self.fig)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self._apply_aesthetics()

    def _apply_aesthetics(self) -> None:
        axes = [self.ax_tl, self.ax_tl_twin, self.ax_tr, self.ax_bl, self.ax_br]
        for ax in axes:
            ax.tick_params(axis='both', which='major', labelsize=10, width=1.5)
            if ax != self.ax_tl_twin:
                ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.6)
        self.fig.tight_layout()

    def plot_hydration_data(
            self,
            time: np.ndarray,
            heat_flow: np.ndarray,
            heat_cumulative: np.ndarray,
            params: Optional[KineticsParameters] = None
    ) -> None:
        self.ax_tl.clear()
        self.ax_tl_twin.clear()
        self.ax_tr.clear()
        self.ax_bl.clear()
        self.ax_br.clear()
        self._apply_aesthetics()

        # ==========================================
        # 1. Top-Left: Global Heat Flow & Cumulative Heat
        # ==========================================
        self.ax_tl.plot(time, heat_flow, color='#2B2F42', linewidth=2.0)
        self.ax_tl_twin.plot(time, heat_cumulative, color='#EF233C', linewidth=2.0)
        self.ax_tl.set_title("1. Global Heat Flow & Cumulative Heat", fontweight='bold', fontsize=11)
        self.ax_tl.set_xlabel('Time (h)', fontweight='bold')
        self.ax_tl.set_ylabel('Heat Flow (mW/g)', fontweight='bold', color='#2B2F42')
        self.ax_tl_twin.yaxis.set_label_position("right")
        self.ax_tl_twin.yaxis.tick_right()
        self.ax_tl_twin.set_ylabel('Cumulative Heat (J/g)', fontweight='bold', color='#EF233C', rotation=270,
                                   labelpad=15)

        # ==========================================
        # 2. Top-Right: Hydration Stages & Peak Features
        # ==========================================
        self.ax_tr.plot(time, heat_flow, color='#2B2F42', linewidth=2.0, label='Heat Flow')
        self.ax_tr.set_title("2. Hydration Stages & Peak Features", fontweight='bold', fontsize=11)
        self.ax_tr.set_xlabel('Time (h)', fontweight='bold')
        self.ax_tr.set_ylabel('Heat Flow (mW/g)', fontweight='bold')

        if params is not None:
            t0 = params.t0_h
            t_peak = params.t_peak_h
            t_end = params.t_end_h

            self.ax_tr.axvspan(0, t0, color='#adb5bd', alpha=0.3, label='Induction')
            self.ax_tr.axvspan(t0, t_peak, color='#EF233C', alpha=0.15, label='Acceleration')
            self.ax_tr.axvspan(t_peak, t_end, color='#4361ee', alpha=0.10, label='Deceleration')
            self.ax_tr.axvline(x=t0, color='#495057', linestyle='--', linewidth=1.5)
            self.ax_tr.axvline(x=t_peak, color='#EF233C', linestyle='--', linewidth=1.5)

            for i, (p_t, p_hf) in enumerate(params.peaks):
                self.ax_tr.plot(p_t, p_hf, marker='^', markersize=8, color='#FF9F1C', markeredgecolor='black', zorder=5)
                self.ax_tr.annotate(f'P{i + 1}', xy=(p_t, p_hf), xytext=(p_t + 1, p_hf + (max(heat_flow) * 0.02)),
                                    fontweight='bold', color='#FF9F1C')
            self.ax_tr.legend(loc='upper right', fontsize=9, framealpha=0.9)

            # ==========================================
            # 3. Bottom-Left: 纯理论动力学机制包络与交点提取
            # ==========================================
            a_th = np.linspace(0.001, 0.999, 2000)
            term_ng = np.maximum(-np.log(1 - a_th), 1e-12)
            f_ng = params.k1 * params.n * (1 - a_th) * (term_ng) ** ((params.n - 1) / params.n)
            f_i = 3 * params.k2 * (1 - a_th) ** (2 / 3)
            denom_d = 2 * (1 - (1 - a_th) ** (1 / 3))
            f_d = np.divide(3 * params.k3 * (1 - a_th) ** (2 / 3), denom_d, out=np.zeros_like(a_th),
                            where=denom_d > 1e-8)

            # 绘制纯粹的理论控制机制线
            self.ax_bl.plot(a_th, f_ng, color='#00CC00', linestyle='-.', linewidth=2.0, label='$F_{NG}(\\alpha)$',
                            zorder=2)
            self.ax_bl.plot(a_th, f_i, color='#FF0000', linestyle='-.', linewidth=2.0, label='$F_I(\\alpha)$', zorder=2)
            self.ax_bl.plot(a_th, f_d, color='#0000FF', linestyle='-.', linewidth=2.0, label='$F_D(\\alpha)$', zorder=2)

            # 绘制机制转换关键交点指引线
            a1, a2 = params.alpha_1, params.alpha_2
            y1 = np.interp(a1, a_th, f_ng)
            y2 = np.interp(a2, a_th, f_i)

            # 绘制粗虚线以及交点圆点，增强数学几何感
            self.ax_bl.plot(a1, y1, 'ko', markersize=8, zorder=4)
            self.ax_bl.plot(a2, y2, 'ko', markersize=8, zorder=4)
            self.ax_bl.vlines(x=a1, ymin=0, ymax=y1, color='black', linestyle='--', linewidth=1.5, zorder=3)
            self.ax_bl.vlines(x=a2, ymin=0, ymax=y2, color='black', linestyle='--', linewidth=1.5, zorder=3)

            # 动态计算理论包络线（取短板），用于决定 Y 轴最佳自适应高度
            f_envelope = np.minimum(f_ng, np.minimum(f_i, f_d))
            y_max_disp = max(f_envelope) if len(f_envelope) > 0 else 0.01
            text_y_offset = y_max_disp * 0.05

            self.ax_bl.annotate(f'$\\alpha_1$={a1:.4f}', xy=(a1, text_y_offset), xytext=(a1 + 0.01, text_y_offset),
                                fontsize=10, fontweight='bold', fontfamily='serif')
            self.ax_bl.annotate(f'$\\alpha_2$={a2:.4f}', xy=(a2, text_y_offset), xytext=(a2 + 0.01, text_y_offset),
                                fontsize=10, fontweight='bold', fontfamily='serif')

            # 视窗自适应缩放，让理论交点置于视窗视觉中心
            max_alpha_disp = min(1.0, a2 + 0.3)
            self.ax_bl.set_xlim(0, max_alpha_disp)
            self.ax_bl.set_ylim(0, y_max_disp * 1.6)  # 预留顶部空间给发散的机制线
            self.ax_bl.grid(False)
            self.ax_bl.legend(loc='upper right', fontsize=10, framealpha=1.0, edgecolor='black')

        self.ax_bl.set_title("3. Theoretical Mechanisms & Intersections", fontweight='bold', fontsize=11)
        self.ax_bl.set_xlabel('$\\alpha$', fontweight='bold', fontsize=12)
        self.ax_bl.set_ylabel('$Rate\\ [h^{-1}]$', fontweight='bold', fontsize=12)

        # ==========================================
        # 4. Bottom-Right: 改造为 Knudsen 线性外推散点图 (文献同款)
        # ==========================================
        self.ax_br.set_title("4. Knudsen Extrapolation Analysis", fontweight='bold', fontsize=11)
        self.ax_br.set_xlabel('$1/(t-t_0)$ $[h^{-1}]$', fontweight='bold')
        self.ax_br.set_ylabel('$1/Q$ $[J^{-1}\cdot g]$', fontweight='bold')

        if params is not None and params.origin_knudsen:
            # 抽取出全量数据与拟合数据
            x_all = params.origin_knudsen.get('X_All: 1/(t-t0) [h^-1]', np.array([]))
            y_all = params.origin_knudsen.get('Y_All: 1/Q [J^-1*g]', np.array([]))
            x_fit = params.origin_knudsen.get('X_Fit: 1/(t-t0) [h^-1]', np.array([]))

            if len(x_all) > 0 and len(y_all) > 0:
                # 1. 绘制形核期的弯曲散点（浅灰虚化处理，证明数据的连续性）
                self.ax_br.plot(x_all, y_all, color='#ced4da', marker='.', markersize=4, linestyle='', alpha=0.6,
                                label='Early Stage')

                # 2. 绘制实际参与后期线性拟合的散点（深黑色高亮，证明算法切入了正确的区域）
                x_fit_valid = x_fit[~np.isnan(x_fit)]
                if len(x_fit_valid) > 0:
                    y_fit_valid = np.interp(x_fit_valid, x_all[::-1], y_all[::-1])
                    self.ax_br.plot(x_fit_valid, y_fit_valid, color='#2B2F42', marker='o', markersize=4, linestyle='',
                                    label='Linear Fit Region')

                # 3. 绘制从 x=0（无穷远时间点）出发的完美数学外推红线
                xmax_view = 0.08  # 论文常规截断视野，过滤掉右侧极端大值
                x_line = np.linspace(0, xmax_view, 100)
                y_line = (1.0 / params.qmax_j_g) + (params.t50_h / params.qmax_j_g) * x_line
                self.ax_br.plot(x_line, y_line, color='red', linestyle='--', linewidth=2.0, label='Extrapolation')

                # 强制约束坐标系视觉域，避免被早期极大数据拉扯导致图形压扁
                self.ax_br.set_xlim(0, xmax_view)
                self.ax_br.set_ylim(0, max(y_line) * 1.1)

                # 将 Qmax 和 t50 打印在图上
                text_info = f"$Q_{{max}}$ = {params.qmax_j_g:.2f} J/g\n$t_{{50}}$ = {params.t50_h:.2f} h"
                self.ax_br.text(0.05, 0.85, text_info, transform=self.ax_br.transAxes,
                                fontsize=10, fontweight='bold',
                                bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

                self.ax_br.legend(loc='lower right', fontsize=9, framealpha=1.0, edgecolor='black')

        self.fig.tight_layout(pad=2.0)
        self.draw()

    def save_individual_plots(self, folder_path: str) -> None:
        p = Path(folder_path)
        p.mkdir(parents=True, exist_ok=True)
        export_configs = [
            (self.ax_tl, "01_Global_Trend.png"),
            (self.ax_tr, "02_Peak_Features.png"),
            (self.ax_bl, "03_Theoretical_Mechanisms.png"),
            (self.ax_br, "04_Knudsen_Extrapolation.png")
        ]
        for ax, name in export_configs:
            extent = ax.get_tightbbox(self.fig.canvas.get_renderer()).transformed(self.fig.dpi_scale_trans.inverted())
            self.fig.savefig(p / name, bbox_inches=extent.expanded(1.2, 1.2), dpi=300)
        self.fig.savefig(p / "Summary_Quad_Plot.png", dpi=300, bbox_inches='tight')