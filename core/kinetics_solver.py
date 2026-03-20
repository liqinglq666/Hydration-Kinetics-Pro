import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy.stats import linregress
from typing import Tuple, List

from core.data_models import HydrationData, KineticsParameters
from utils.exceptions import KineticsCalculationError
from utils.logger import logger


class KDSolver:
    """
    Krstulovic-Dabic 动力学核心求解引擎。
    恢复了严格的物理斜率约束 (force_slope_1)，彻底修复机制坍塌重叠与 Qmax 外推失效问题。
    """

    def __init__(self, data: HydrationData, expected_peaks: int = 1) -> None:
        self.data = data
        self.expected_peaks = expected_peaks

    def execute_pipeline(self) -> KineticsParameters:
        t0 = self._detect_t0()
        t_peak = self._detect_main_peak(t0)

        all_peaks = self._extract_all_peaks()

        # 修复 1：重构 Knudsen 获取最高置信度的 Qmax
        qmax, t50, dict_knudsen = self._calculate_knudsen(t0, t_peak)

        # 修复 2：带刚性物理斜率约束的寻优
        k1, n, k2, k3, alpha_1, alpha_2, r2_ng, r2_i, r2_d, dict_linear = self._integral_domain_linear_fitting(t0,
                                                                                                               t_peak)

        mask_rate = self.data.time_h > t0
        a_valid = np.clip(self.data.alpha[mask_rate], 1e-8, 0.999)
        rate_exp = (self.data.heat_flow_mw_g[mask_rate] * 3.6) / qmax

        term_ng = np.clip(-np.log(1.0 - a_valid), 1e-12, None)
        f_ng = k1 * n * (1.0 - a_valid) * (term_ng ** ((n - 1.0) / n))
        f_i = 3.0 * k2 * ((1.0 - a_valid) ** (2.0 / 3.0))
        denom_d = 2.0 * (1.0 - (1.0 - a_valid) ** (1.0 / 3.0))
        f_d = np.divide(
            3.0 * k3 * ((1.0 - a_valid) ** (2.0 / 3.0)),
            denom_d,
            out=np.zeros_like(a_valid),
            where=(denom_d > 1e-8)
        )

        dict_rates = {
            'X: Alpha (水化度)': a_valid,
            'Y1: Exp_Rate [h^-1]': rate_exp,
            'Y2: F_NG [h^-1]': f_ng,
            'Y3: F_I [h^-1]': f_i,
            'Y4: F_D [h^-1]': f_d
        }

        if np.sum(mask_rate) > 10:
            time_valid = self.data.time_h[mask_rate]
            alpha_mono = np.maximum.accumulate(self.data.alpha[mask_rate])
            t_a1 = float(np.interp(alpha_1, alpha_mono, time_valid))
            t_a2 = float(np.interp(alpha_2, alpha_mono, time_valid))
        else:
            t_a1, t_a2 = t0, t0

        t_end = float(self.data.time_h[-1])
        d_alpha = max(0.0, alpha_2 - alpha_1)
        d_time = max(0.0, t_a2 - t_a1)

        return KineticsParameters(
            t0_h=t0, qmax_j_g=qmax, t50_h=t50,
            n=n, k1=k1, k2=k2, k3=k3,
            r2_ng=r2_ng, r2_i=r2_i, r2_d=r2_d,
            alpha_1=alpha_1, alpha_2=alpha_2,
            t_alpha_1_h=t_a1, t_alpha_2_h=t_a2,
            delta_alpha=d_alpha, delta_time_h=d_time,
            t_peak_h=t_peak, t_end_h=t_end,
            induction_duration_h=t0,
            accel_duration_h=max(0.0, t_peak - t0),
            decel_duration_h=max(0.0, t_end - t_peak),
            peaks=all_peaks,
            origin_knudsen=dict_knudsen,
            origin_kd_linear=dict_linear,
            origin_rates=dict_rates
        )

    def _extract_all_peaks(self) -> List[Tuple[float, float]]:
        heat_flow = self.data.heat_flow_mw_g
        time_h = self.data.time_h

        if len(time_h) < 10:
            return []

        dt = float(np.median(np.diff(time_h)))
        if dt <= 0: raise ValueError("时间序列非单调递增，存在数据脏读。")

        points_per_hour = int(1.0 / dt)
        window = int(max(5, points_per_hour | 1))
        window = min(window, len(heat_flow) // 4 | 1)

        try:
            hf_smooth = savgol_filter(heat_flow, window_length=window, polyorder=3)
        except ValueError:
            hf_smooth = heat_flow

        candidates_idx: List[int] = []
        min_dist_idx = max(1, int(1.5 / dt))

        mask_main = time_h > 1.5
        if np.sum(mask_main) > 0:
            idx_main = int(np.argmax(hf_smooth[mask_main]) + np.where(mask_main)[0][0])
            candidates_idx.append(idx_main)
            main_peak_h = float(hf_smooth[idx_main])
        else:
            return []

        idx_raw, _ = find_peaks(hf_smooth, distance=min_dist_idx, prominence=main_peak_h * 0.01)
        for i in idx_raw:
            if time_h[i] > 1.5 and i not in candidates_idx: candidates_idx.append(i)

        deriv = np.gradient(hf_smooth, dt)
        try:
            deriv_smooth = savgol_filter(deriv, window_length=window, polyorder=2)
        except ValueError:
            deriv_smooth = deriv

        idx_deriv, props_deriv = find_peaks(deriv_smooth, prominence=0)
        valid_deriv_idx, valid_deriv_prom = [], []
        for i, prom in zip(idx_deriv, props_deriv['prominences']):
            if time_h[i] > time_h[idx_main] and hf_smooth[i] > main_peak_h * 0.05:
                valid_deriv_idx.append(i)
                valid_deriv_prom.append(prom)

        if valid_deriv_idx:
            sorted_deriv_pairs = sorted(zip(valid_deriv_prom, valid_deriv_idx), reverse=True)
            for idx in [i for _, i in sorted_deriv_pairs[:3]]:
                if idx not in candidates_idx: candidates_idx.append(idx)

        candidates_idx.sort()
        filtered_idx: List[int] = []
        for c in candidates_idx:
            if not filtered_idx:
                filtered_idx.append(c)
            else:
                if (time_h[c] - time_h[filtered_idx[-1]]) < 1.5:
                    if hf_smooth[c] > hf_smooth[filtered_idx[-1]]: filtered_idx[-1] = c
                else:
                    filtered_idx.append(c)

        if len(filtered_idx) > self.expected_peaks:
            filtered_idx = sorted(filtered_idx, key=lambda i: hf_smooth[i], reverse=True)[:self.expected_peaks]
            filtered_idx.sort()

        return [(float(time_h[idx]), float(heat_flow[idx])) for idx in filtered_idx]

    def _detect_t0(self, search_window: Tuple[float, float] = (0.2, 10.0)) -> float:
        mask = (self.data.time_h >= search_window[0]) & (self.data.time_h <= search_window[1])
        t_win = self.data.time_h[mask]
        hf_win = self.data.heat_flow_mw_g[mask]

        if len(t_win) < 5: raise KineticsCalculationError("t0 搜索区间有效数据不足。")

        dt = float(np.median(np.diff(self.data.time_h)))
        window_length = min(31, int(1.0 / dt) | 1) if dt > 0 else 31
        window_length = min(window_length, len(hf_win) // 2 * 2 + 1)

        if window_length > 3:
            try:
                hf_smoothed = savgol_filter(hf_win, window_length=window_length, polyorder=2)
            except ValueError:
                hf_smoothed = hf_win
        else:
            hf_smoothed = hf_win

        return float(t_win[np.argmin(hf_smoothed)])

    def _detect_main_peak(self, t0: float) -> float:
        mask = self.data.time_h > t0
        t_valid = self.data.time_h[mask]
        hf_valid = self.data.heat_flow_mw_g[mask]
        if len(t_valid) == 0: return t0

        dt = float(np.median(np.diff(self.data.time_h)))
        window = min(51, int(1.5 / dt) | 1) if dt > 0 else 51
        window = min(window, len(hf_valid) // 5 | 1)

        if window > 3:
            try:
                hf_smoothed = savgol_filter(hf_valid, window_length=window, polyorder=2)
            except ValueError:
                hf_smoothed = hf_valid
        else:
            hf_smoothed = hf_valid

        return float(t_valid[np.argmax(hf_smoothed)])

    def _calculate_knudsen(self, t0: float, t_peak: float) -> Tuple[float, float, dict]:
        mask = self.data.time_h > t0
        t_valid = self.data.time_h[mask]

        q_at_t0 = float(np.interp(t0, self.data.time_h, self.data.cumulative_heat_j_g))
        q_valid = self.data.cumulative_heat_j_g[mask] - q_at_t0

        valid_idx = q_valid > 0
        t_calc = t_valid[valid_idx]
        q_calc = q_valid[valid_idx]

        if len(t_calc) < 10: raise ValueError("有效量热数据点不足，无法执行 Knudsen 外推。")

        x_all = 1.0 / (t_calc - t0)
        y_all = 1.0 / q_calc

        total_time = t_calc[-1]

        # 核心修复 1：严格把控 Knudsen 尾端切片 (杜绝弯曲数据污染直线)
        # 对于 72h 以内的短时测试，死死咬住最后 24 小时；长时测试咬住最后 48 小时
        if total_time < 96.0:
            t_threshold = max(t_peak + 12.0, total_time - 24.0)
        else:
            t_threshold = max(t_peak + 24.0, total_time - 48.0)

        fit_mask = (t_calc > t_threshold)

        # 防御机制：如果截取的数据点太少，放宽到末端 30%
        if np.sum(fit_mask) < 10:
            fit_mask = t_calc > (total_time * 0.7)

        x_fit = x_all[fit_mask]
        y_fit = y_all[fit_mask]

        slope, intercept, _, _, _ = linregress(x_fit, y_fit)

        # 核心修复 2：强化 Qmax 物理边界拦截
        # 如果拟合出负截距，或者算出的 Qmax 只比实验末期热量大一点点 (<5%)，说明曲线未伸平
        q_final = np.max(q_calc)
        if intercept <= 0 or slope <= 0 or np.isnan(intercept) or (1.0 / intercept < q_final * 1.05):
            logger.warning(f"Knudsen 提前截断或拟合塌陷。触发理论热量补偿 (Q_final * 1.15)。")
            qmax = float(q_final * 1.15)  # 根据 FA/GBFS 体系反应后期潜力，给予 15% 的外推补偿
            t50 = float(t_calc[np.argmin(np.abs(q_calc - qmax / 2.0))] - t0)
        else:
            qmax = float(1.0 / intercept)
            t50 = float(slope * qmax)
            # 异常检查：防止因为局部毛刺算出荒谬极大值
            if qmax > q_final * 5.0:
                qmax = float(q_final * 1.15)
                t50 = float(t_calc[np.argmin(np.abs(q_calc - qmax / 2.0))] - t0)

        self.data.alpha = np.zeros_like(self.data.time_h)
        self.data.alpha[mask] = q_calc / qmax

        max_len = len(x_all)
        dict_knudsen = {
            'X_All: 1/(t-t0) [h^-1]': x_all,
            'Y_All: 1/Q [J^-1*g]': y_all,
            'X_Fit: 1/(t-t0) [h^-1]': np.pad(x_fit, (0, max_len - len(x_fit)), constant_values=np.nan),
            'Y_Fit: 1/Q [J^-1*g]': np.pad(y_fit, (0, max_len - len(y_fit)), constant_values=np.nan)
        }
        return qmax, t50, dict_knudsen

    def _find_boundaries(self, k1: float, n: float, k2: float, k3: float, a_peak: float) -> Tuple[float, float]:
        a_scan = np.linspace(0.005, 0.995, 2000)

        term_ng = np.clip(-np.log(1.0 - a_scan), 1e-12, None)
        f_ng = k1 * n * (1.0 - a_scan) * (term_ng ** ((n - 1.0) / n))
        f_i = 3.0 * k2 * ((1.0 - a_scan) ** (2.0 / 3.0))
        denom_d = 2.0 * (1.0 - (1.0 - a_scan) ** (1.0 / 3.0))
        f_d = np.divide(3.0 * k3 * ((1.0 - a_scan) ** (2.0 / 3.0)), denom_d, out=np.full_like(a_scan, np.nan),
                        where=(denom_d > 1e-8))

        diff_1 = f_ng - f_i
        crossings_1 = np.where(np.diff(np.sign(diff_1)))[0]
        alpha_1 = float(a_scan[crossings_1[0]]) if crossings_1.size > 0 else float(a_peak)

        diff_2 = f_i - f_d
        crossings_2 = np.where(np.diff(np.sign(diff_2)))[0]
        valid_crossings_2 = [idx for idx in crossings_2 if a_scan[idx] > alpha_1]

        if valid_crossings_2:
            alpha_2 = float(a_scan[valid_crossings_2[0]])
        else:
            alpha_2 = float(min(0.85, alpha_1 + 0.15))

        return alpha_1, alpha_2

    def _find_best_linear_segment_fixed_slope(self, x: np.ndarray, y: np.ndarray, min_ratio: float = 0.25,
                                              force_slope_1: bool = False) -> Tuple[
        float, float, float, np.ndarray, np.ndarray]:
        """
        核心物理求解器。
        【重新启用 force_slope_1】: 坚决捍卫 K-D 模型的几何基础。
        通过跨度奖励机制，自动寻找符合“理论斜率1”的最优长区间。
        """
        valid_mask = ~(np.isnan(x) | np.isnan(y) | np.isinf(x) | np.isinf(y))
        x_val = x[valid_mask]
        y_val = y[valid_mask]
        n_pts = len(x_val)

        min_pts = max(10, int(n_pts * min_ratio))
        if n_pts < min_pts: return 1.0, 0.0, 0.0, np.array([]), np.array([])

        best_metric = -float('inf')
        best_slice = slice(0, n_pts)

        step = max(1, n_pts // 50)
        for i in range(0, n_pts - min_pts + 1, step):
            for j in range(i + min_pts, n_pts + 1, step):
                x_sub = x_val[i:j]
                y_sub = y_val[i:j]
                coverage = (j - i) / n_pts

                # 核心修复 3：区分自由拟合与强制物理拟合
                if force_slope_1:
                    intercept = np.mean(y_sub - x_sub)
                    y_pred = x_sub + intercept
                    ss_res = np.sum((y_sub - y_pred) ** 2)
                    ss_tot = np.sum((y_sub - np.mean(y_sub)) ** 2)
                    r2_raw = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
                else:
                    if len(x_sub) > 2:
                        corr = np.corrcoef(x_sub, y_sub)[0, 1]
                        r2_raw = corr ** 2 if not np.isnan(corr) else 0.0
                    else:
                        r2_raw = 0.0

                if r2_raw > 0:
                    metric = r2_raw * (coverage ** 0.1)
                else:
                    metric = 0.0

                if metric > best_metric:
                    best_metric = metric
                    best_slice = slice(i, j)

        x_best = x_val[best_slice]
        y_best = y_val[best_slice]

        # 计算最终提取区间的参数
        if force_slope_1:
            slope_f = 1.0
            int_f = float(np.mean(y_best - x_best))
            y_pred = x_best + int_f
            ss_res = np.sum((y_best - y_pred) ** 2)
            ss_tot = np.sum((y_best - np.mean(y_best)) ** 2)
            r2_f = float(max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0)
        else:
            slope_f, int_f, r_val_f, _, _ = linregress(x_best, y_best)
            r2_f = float(r_val_f ** 2)

        return slope_f, int_f, r2_f, x_best, y_best

    def _integral_domain_linear_fitting(self, t0: float, t_peak: float) -> Tuple[
        float, float, float, float, float, float, float, float, float, dict]:

        mask = (self.data.time_h > t0) & (self.data.alpha > 0.02) & (self.data.alpha < 0.90)
        t_delta = self.data.time_h[mask] - t0
        alpha = self.data.alpha[mask]
        dict_linear = {}

        if len(alpha) < 10:
            return 0.05, 2.0, 0.005, 0.0005, 0.25, 0.65, 0.0, 0.0, 0.0, {}

        a_peak = float(np.interp(t_peak, self.data.time_h, self.data.alpha))
        alpha_max = alpha.max()

        # ================== 1. NG 阶段 ==================
        m_ng = alpha <= (a_peak * 0.95)
        if np.sum(m_ng) > 10:
            x_ng_raw = np.log(t_delta[m_ng])
            y_ng_raw = np.log(-np.log(1.0 - alpha[m_ng]))

            slope_ng, int_ng, r2_ng, x_ng_fit, y_ng_fit = self._find_best_linear_segment_fixed_slope(
                x_ng_raw, y_ng_raw, min_ratio=0.3, force_slope_1=False)

            n = float(np.clip(slope_ng, 0.5, 5.0))
            k1 = float(np.clip(np.exp(int_ng / n), 1e-6, 1.0))
            dict_linear['[NG] X: ln(t-t0)'] = x_ng_fit
            dict_linear['[NG] Y: ln(-ln(1-α))'] = y_ng_fit
        else:
            n, k1, r2_ng = 2.0, 0.05, 0.0
            dict_linear['[NG] X: ln(t-t0)'] = dict_linear['[NG] Y: ln(-ln(1-α))'] = np.array([])

        # ================== 2. I 阶段 (强约束寻域) ==================
        # 扩大 I 阶段的搜索域，让算法有更充足的数据量去寻找斜率为 1 的纯净片段
        a_mid = min(a_peak + 0.30, alpha_max * 0.80)
        m_i = (alpha > a_peak) & (alpha <= a_mid)
        if np.sum(m_i) > 10:
            x_i_raw = np.log(t_delta[m_i])
            y_i_raw = np.log(1.0 - (1.0 - alpha[m_i]) ** (1.0 / 3.0))

            # 必须开启 force_slope_1=True，保卫物理底线！
            slope_i, int_i, r2_i, x_i_fit, y_i_fit = self._find_best_linear_segment_fixed_slope(
                x_i_raw, y_i_raw, min_ratio=0.25, force_slope_1=True)

            k2 = float(np.clip(np.exp(int_i), 1e-7, 1.0))
            dict_linear['[I] X: ln(t-t0)'] = x_i_fit
            dict_linear['[I] Y: ln(1-(1-α)^1/3)'] = y_i_fit
        else:
            k2, r2_i = 0.005, 0.0
            dict_linear['[I] X: ln(t-t0)'] = dict_linear['[I] Y: ln(1-(1-α)^1/3)'] = np.array([])

        # ================== 3. D 阶段 (强约束寻域) ==================
        # 允许扩散期从极早期（峰后）就开始寻找可能的扩散控制带
        m_d = (alpha > a_peak + 0.10) & (alpha <= alpha_max * 0.95)
        if np.sum(m_d) > 10:
            x_d_raw = np.log(t_delta[m_d])
            y_d_raw = 2.0 * np.log(1.0 - (1.0 - alpha[m_d]) ** (1.0 / 3.0))

            # 必须开启 force_slope_1=True
            slope_d, int_d, r2_d, x_d_fit, y_d_fit = self._find_best_linear_segment_fixed_slope(
                x_d_raw, y_d_raw, min_ratio=0.20, force_slope_1=True)

            k3 = float(np.clip(np.exp(int_d), 1e-8, 1.0))
            dict_linear['[D] X: ln(t-t0)'] = x_d_fit
            dict_linear['[D] Y: 2*ln(1-(1-α)^1/3)'] = y_d_fit
        else:
            k3, r2_d = 0.0005, 0.0
            dict_linear['[D] X: ln(t-t0)'] = dict_linear['[D] Y: 2*ln(1-(1-α)^1/3)'] = np.array([])

        a1, a2 = self._find_boundaries(k1, n, k2, k3, a_peak)

        return k1, n, k2, k3, a1, a2, r2_ng, r2_i, r2_d, dict_linear