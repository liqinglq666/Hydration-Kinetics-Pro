from typing import List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks, savgol_filter
from scipy.stats import linregress

from core.data_models import HydrationData, KineticsParameters
from utils.exceptions import KineticsCalculationError
from utils.logger import logger


class KDSolver:
    """
    Krstulovic-Dabic 动力学核心求解引擎。

    关键原则：
    1. 不在数据不足时返回看似真实的默认参数。
    2. 拟合失败必须显式报错，避免用户把 fallback 当作论文结果。
    3. 允许 Knudsen 理论热量补偿，但所有 K-D 分段参数必须来自有效数据窗口。
    4. K-D 分段窗口采用“物理窗口优先 + 数据驱动扩展”，避免窄窗口误伤平滑曲线。
    5. 允许用户手动指定 t0 与总累计极限热量 Q∞，并完整记录来源。
    """

    def __init__(
        self,
        data: HydrationData,
        expected_peaks: int = 1,
        manual_t0_h: Optional[float] = None,
        manual_qmax_total_j_g: Optional[float] = None,
        allow_qmax_fallback: bool = True,
    ) -> None:
        self.data = data
        self.expected_peaks = int(expected_peaks)
        self.manual_t0_h = None if manual_t0_h is None else float(manual_t0_h)
        self.manual_qmax_total_j_g = None if manual_qmax_total_j_g is None else float(manual_qmax_total_j_g)
        self.allow_qmax_fallback = bool(allow_qmax_fallback)
        self.warnings: List[str] = []
        if self.expected_peaks < 1:
            raise KineticsCalculationError("预期特征峰数必须至少为 1。")

    def execute_pipeline(self) -> KineticsParameters:
        self._validate_input_data()

        if self.manual_t0_h is None:
            t0 = self._detect_t0()
            t0_method = "auto_min_heat_flow"
        else:
            t0 = self._validate_manual_t0(self.manual_t0_h)
            t0_method = "manual"

        t_peak = self._detect_main_peak(t0)
        all_peaks = self._extract_all_peaks()

        (
            qmax,
            t50,
            q_at_t0,
            qmax_total,
            dict_knudsen,
            qmax_fallback_used,
            qmax_method,
            r2_knudsen,
        ) = self._calculate_qmax(t0, t_peak)
        if not np.isfinite(qmax) or qmax <= 0:
            raise KineticsCalculationError("Qmax 计算失败，无法继续 K-D 动力学分析。")

        k1, n, k2, k3, alpha_1, alpha_2, r2_ng, r2_i, r2_d, dict_linear = self._integral_domain_linear_fitting(
            t0, t_peak, qmax
        )

        mask_rate = self.data.time_h > t0
        if np.sum(mask_rate) < 10:
            raise KineticsCalculationError("t0 之后有效数据点不足，无法生成理论速率包络线。")

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
            where=(denom_d > 1e-8),
        )

        dict_rates = {
            "X: Alpha (水化度)": a_valid,
            "Y1: Exp_Rate [h^-1]": rate_exp,
            "Y2: F_NG [h^-1]": f_ng,
            "Y3: F_I [h^-1]": f_i,
            "Y4: F_D [h^-1]": f_d,
        }

        time_valid = self.data.time_h[mask_rate]
        alpha_mono = np.maximum.accumulate(self.data.alpha[mask_rate])
        t_a1 = float(np.interp(alpha_1, alpha_mono, time_valid))
        t_a2 = float(np.interp(alpha_2, alpha_mono, time_valid))

        t_end = float(self.data.time_h[-1])
        d_alpha = max(0.0, alpha_2 - alpha_1)
        d_time = max(0.0, t_a2 - t_a1)

        return KineticsParameters(
            t0_h=t0,
            qmax_j_g=qmax,
            t50_h=t50,
            n=n,
            k1=k1,
            k2=k2,
            k3=k3,
            r2_ng=r2_ng,
            r2_i=r2_i,
            r2_d=r2_d,
            r2_knudsen=r2_knudsen,
            alpha_1=alpha_1,
            alpha_2=alpha_2,
            t_alpha_1_h=t_a1,
            t_alpha_2_h=t_a2,
            delta_alpha=d_alpha,
            delta_time_h=d_time,
            t_peak_h=t_peak,
            t_end_h=t_end,
            induction_duration_h=t0,
            accel_duration_h=max(0.0, t_peak - t0),
            decel_duration_h=max(0.0, t_end - t_peak),
            peaks=all_peaks,
            input_mode=getattr(self.data, "input_mode", "unknown"),
            detected_unit_mode=getattr(self.data, "detected_unit_mode", None),
            sample_mass_g=getattr(self.data, "sample_mass_g", 1.0),
            t0_method=t0_method,
            manual_t0_h=self.manual_t0_h,
            q_at_t0_j_g=q_at_t0,
            qmax_total_j_g=qmax_total,
            manual_qmax_total_j_g=self.manual_qmax_total_j_g,
            qmax_method=qmax_method,
            qmax_fallback_used=qmax_fallback_used,
            qmax_fallback_allowed=self.allow_qmax_fallback,
            warnings=list(dict.fromkeys(self.warnings)),
            origin_knudsen=dict_knudsen,
            origin_kd_linear=dict_linear,
            origin_rates=dict_rates,
        )

    def _add_warning(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)

    def _validate_input_data(self) -> None:
        n = len(self.data.time_h)
        if n < 20:
            raise KineticsCalculationError("量热数据点过少，建议使用至少覆盖 72 h 的连续数据。")
        if not (len(self.data.heat_flow_mw_g) == n and len(self.data.cumulative_heat_j_g) == n):
            raise KineticsCalculationError("时间、热流、累计热量数组长度不一致。")
        if not np.all(np.isfinite(self.data.time_h)):
            raise KineticsCalculationError("时间列包含 NaN 或无穷值。")
        if not np.all(np.diff(self.data.time_h) > 0):
            raise KineticsCalculationError("时间列必须严格递增。")
        if not np.all(np.isfinite(self.data.heat_flow_mw_g)) or not np.all(np.isfinite(self.data.cumulative_heat_j_g)):
            raise KineticsCalculationError("热流或累计热量列包含 NaN 或无穷值。")
        if np.nanmax(self.data.cumulative_heat_j_g) <= 0:
            raise KineticsCalculationError("累计热量必须包含正值。")
        if np.any(np.diff(self.data.cumulative_heat_j_g) < -1e-6):
            self._add_warning("累计热量存在局部下降，可能来自仪器噪声、基线校正或单位列选择错误；请复查原始数据。")

    def _extract_all_peaks(self) -> List[Tuple[float, float]]:
        heat_flow = self.data.heat_flow_mw_g
        time_h = self.data.time_h
        if len(time_h) < 10:
            return []
        dt = float(np.median(np.diff(time_h)))
        if dt <= 0:
            raise KineticsCalculationError("时间序列非单调递增。")
        points_per_hour = max(1, int(1.0 / dt))
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

        idx_raw, _ = find_peaks(hf_smooth, distance=min_dist_idx, prominence=max(main_peak_h * 0.01, 1e-12))
        for i in idx_raw:
            if time_h[i] > 1.5 and i not in candidates_idx:
                candidates_idx.append(i)

        candidates_idx.sort()
        filtered_idx: List[int] = []
        for c in candidates_idx:
            if not filtered_idx:
                filtered_idx.append(c)
            elif (time_h[c] - time_h[filtered_idx[-1]]) < 1.5:
                if hf_smooth[c] > hf_smooth[filtered_idx[-1]]:
                    filtered_idx[-1] = c
            else:
                filtered_idx.append(c)

        if len(filtered_idx) > self.expected_peaks:
            filtered_idx = sorted(filtered_idx, key=lambda i: hf_smooth[i], reverse=True)[: self.expected_peaks]
            filtered_idx.sort()
        return [(float(time_h[idx]), float(heat_flow[idx])) for idx in filtered_idx]

    def _validate_manual_t0(self, t0: float) -> float:
        if not np.isfinite(t0):
            raise KineticsCalculationError("手动 t0 必须是有限数值。")
        t_min = float(self.data.time_h[0])
        t_max = float(self.data.time_h[-1])
        if t0 < t_min or t0 >= t_max:
            raise KineticsCalculationError(f"手动 t0={t0:g} h 超出数据时间范围 [{t_min:g}, {t_max:g}) h。")
        if np.sum(self.data.time_h > t0) < 20:
            raise KineticsCalculationError("手动 t0 之后有效数据点过少，无法进行 K-D 拟合。")
        q_at_t0 = float(np.interp(t0, self.data.time_h, self.data.cumulative_heat_j_g))
        q_after = self.data.cumulative_heat_j_g[self.data.time_h > t0] - q_at_t0
        if np.nanmax(q_after) <= 0:
            raise KineticsCalculationError("手动 t0 之后累计放热没有正增长，请检查 t0 是否过晚。")
        logger.info(f"使用手动 t0: {t0:.4f} h。")
        return float(t0)

    def _detect_t0(self, search_window: Tuple[float, float] = (0.2, 10.0)) -> float:
        mask = (self.data.time_h >= search_window[0]) & (self.data.time_h <= search_window[1])
        t_win = self.data.time_h[mask]
        hf_win = self.data.heat_flow_mw_g[mask]
        if len(t_win) < 5:
            raise KineticsCalculationError("t0 搜索窗口内数据不足。")
        dt = float(np.median(np.diff(self.data.time_h)))
        if dt <= 0:
            raise KineticsCalculationError("时间序列非单调递增。")
        window_length = min(31, int(1.0 / dt) | 1)
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
        if len(t_valid) == 0:
            raise KineticsCalculationError("t0 之后无有效热流数据。")
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

    def _calculate_qmax(self, t0: float, t_peak: float) -> Tuple[float, float, float, float, dict, bool, str, float]:
        mask = self.data.time_h > t0
        t_valid = self.data.time_h[mask]

        q_at_t0 = float(np.interp(t0, self.data.time_h, self.data.cumulative_heat_j_g))
        q_valid = self.data.cumulative_heat_j_g[mask] - q_at_t0

        valid_idx = q_valid > 0
        t_calc = t_valid[valid_idx]
        q_calc = q_valid[valid_idx]

        if len(t_calc) < 10:
            raise KineticsCalculationError("Knudsen 外推所需的有效量热数据不足。请使用更完整的中后期水化数据。")

        x_all = 1.0 / (t_calc - t0)
        y_all = 1.0 / q_calc
        total_time = t_calc[-1]

        t_threshold = max(t_peak * 2.0, t0 + 12.0)
        t_threshold = min(t_threshold, total_time * 0.6)
        fit_mask = t_calc > t_threshold

        if np.sum(fit_mask) < 10:
            fit_mask = t_calc > (total_time * 0.7)

        if np.sum(fit_mask) < 3:
            raise KineticsCalculationError("Knudsen 拟合窗口数据点不足，无法可靠外推 Qmax。")

        x_fit = x_all[fit_mask]
        y_fit = y_all[fit_mask]
        if len(np.unique(x_fit)) < 2:
            raise KineticsCalculationError("Knudsen 拟合窗口时间点重复，无法线性回归。")

        slope, intercept, r_value, _, _ = linregress(x_fit, y_fit)
        r2_knudsen = float(r_value**2) if np.isfinite(r_value) else 0.0
        q_final = float(np.max(q_calc))
        qmax_fallback_used = False

        if self.manual_qmax_total_j_g is not None:
            if not np.isfinite(self.manual_qmax_total_j_g) or self.manual_qmax_total_j_g <= 0:
                raise KineticsCalculationError("手动 Q∞ 必须是大于 0 的有限数值，单位为 J/g。")
            qmax = float(self.manual_qmax_total_j_g - q_at_t0)
            if qmax <= q_final:
                raise KineticsCalculationError(
                    "手动 Q∞ 不足：Q∞ - Q(t0) 必须大于 t0 后当前最大累计放热。"
                    f"当前 Q(t0)={q_at_t0:.4f} J/g，t0 后 Q_final={q_final:.4f} J/g。"
                )
            t50 = float(t_calc[np.argmin(np.abs(q_calc - qmax / 2.0))] - t0)
            qmax_total = float(self.manual_qmax_total_j_g)
            qmax_method = "manual_total_cumulative_heat_qinf"
            logger.info(f"使用手动 Q∞={self.manual_qmax_total_j_g:.4f} J/g；t0 后有效 Qmax={qmax:.4f} J/g。")
        elif intercept <= 0 or slope <= 0 or np.isnan(intercept) or (1.0 / intercept < q_final * 1.05):
            if not self.allow_qmax_fallback:
                raise KineticsCalculationError(
                    "Knudsen 宏观拟合失效，且已关闭 Q_final × 1.15 fallback。请手动指定 Q∞ 或检查后期数据。"
                )
            self._add_warning("Knudsen 宏观拟合失效，Qmax 使用 Q_final * 1.15 保守补偿；请谨慎解释 Qmax 与 t50。")
            qmax = float(q_final * 1.15)
            t50 = float(t_calc[np.argmin(np.abs(q_calc - qmax / 2.0))] - t0)
            qmax_total = float(q_at_t0 + qmax)
            qmax_fallback_used = True
            qmax_method = "fallback_q_final_x_1.15"
        else:
            qmax = float(1.0 / intercept)
            t50 = float(slope * qmax)
            qmax_total = float(q_at_t0 + qmax)
            qmax_method = "knudsen_linear_extrapolation"
            if qmax > q_final * 5.0 or not np.isfinite(t50) or t50 <= 0:
                if not self.allow_qmax_fallback:
                    raise KineticsCalculationError(
                        "Knudsen 外推发散，且已关闭 Q_final × 1.15 fallback。请手动指定 Q∞ 或检查后期数据。"
                    )
                self._add_warning("Knudsen 外推发散，Qmax 使用 Q_final * 1.15 保守补偿；请谨慎解释 Qmax 与 t50。")
                qmax = float(q_final * 1.15)
                t50 = float(t_calc[np.argmin(np.abs(q_calc - qmax / 2.0))] - t0)
                qmax_total = float(q_at_t0 + qmax)
                qmax_fallback_used = True
                qmax_method = "fallback_q_final_x_1.15"

        alpha_valid = np.zeros_like(q_valid, dtype=float)
        alpha_valid[valid_idx] = q_calc / qmax
        self.data.alpha = np.zeros_like(self.data.time_h, dtype=float)
        self.data.alpha[mask] = alpha_valid

        max_len = len(x_all)
        dict_knudsen = {
            "X_All: 1/(t-t0) [h^-1]": x_all,
            "Y_All: 1/Q [J^-1*g]": y_all,
            "X_Fit: 1/(t-t0) [h^-1]": np.pad(x_fit, (0, max_len - len(x_fit)), constant_values=np.nan),
            "Y_Fit: 1/Q [J^-1*g]": np.pad(y_fit, (0, max_len - len(y_fit)), constant_values=np.nan),
        }

        return qmax, t50, q_at_t0, qmax_total, dict_knudsen, qmax_fallback_used, qmax_method, r2_knudsen

    def _find_boundaries(self, k1: float, n: float, k2: float, k3: float, a_peak: float) -> Tuple[float, float]:
        a_scan = np.linspace(0.005, 0.995, 2000)
        term_ng = np.clip(-np.log(1.0 - a_scan), 1e-12, None)
        f_ng = k1 * n * (1.0 - a_scan) * (term_ng ** ((n - 1.0) / n))
        f_i = 3.0 * k2 * ((1.0 - a_scan) ** (2.0 / 3.0))
        denom_d = 2.0 * (1.0 - (1.0 - a_scan) ** (1.0 / 3.0))
        f_d = np.divide(
            3.0 * k3 * ((1.0 - a_scan) ** (2.0 / 3.0)),
            denom_d,
            out=np.full_like(a_scan, np.nan),
            where=(denom_d > 1e-8),
        )

        f_envelope = np.minimum(np.minimum(f_ng, f_i), f_d)
        is_ng_dominant = np.isclose(f_envelope, f_ng, rtol=1e-3, atol=1e-5)
        is_d_dominant = np.isclose(f_envelope, f_d, rtol=1e-3, atol=1e-5)

        ng_end_idx = np.where(~is_ng_dominant)[0]
        alpha_1 = float(a_scan[ng_end_idx[0]]) if ng_end_idx.size > 0 else float(a_peak)

        d_start_idx = np.where(is_d_dominant & (a_scan >= alpha_1))[0]
        alpha_2 = float(a_scan[d_start_idx[0]]) if d_start_idx.size > 0 else min(0.85, alpha_1 + 0.10)

        if alpha_2 <= alpha_1 + 0.01:
            logger.info("物理跃迁判定：体系发生 NG -> D 机制跨越，I 阶段被压缩至无。")
            alpha_2 = alpha_1

        return alpha_1, alpha_2

    def _stage_mask(
        self,
        alpha: np.ndarray,
        lower: float,
        upper: float,
        fallback_lower: float,
        fallback_upper: float,
        center: float,
        min_points: int,
        label: str,
    ) -> np.ndarray:
        """Select a fitting window without fabricating parameters."""
        alpha_max = float(np.nanmax(alpha))
        candidates = [
            (max(0.01, lower), min(0.97, upper), "physical"),
            (max(0.01, fallback_lower), min(0.97, fallback_upper), "expanded"),
            (max(0.01, alpha_max * 0.20), min(0.97, alpha_max * 0.92), "broad"),
        ]

        for lo, hi, stage_mode in candidates:
            if hi <= lo:
                continue
            mask = (alpha >= lo) & (alpha <= hi)
            if int(np.sum(mask)) >= min_points:
                if stage_mode != "physical":
                    self._add_warning(f"{label} 阶段物理窗口点数不足，已使用 {stage_mode} alpha 窗口参与拟合。")
                return mask

        valid = np.where((alpha > 0.01) & (alpha < min(0.97, alpha_max * 0.97)))[0]
        if len(valid) < min_points:
            raise KineticsCalculationError(f"{label} 阶段有效点不足，无法拟合对应动力学参数。")

        center = float(np.clip(center, np.nanmin(alpha[valid]), np.nanmax(alpha[valid])))
        nearest = valid[np.argsort(np.abs(alpha[valid] - center))[:min_points]]
        mask = np.zeros_like(alpha, dtype=bool)
        mask[np.sort(nearest)] = True
        self._add_warning(f"{label} 阶段物理窗口点数不足，已使用邻近 alpha 点扩展拟合窗口。")
        return mask

    def _safe_r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
        return float(max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0)

    def _integral_domain_linear_fitting(self, t0: float, t_peak: float, qmax: float) -> Tuple[
        float, float, float, float, float, float, float, float, float, dict
    ]:
        mask = (self.data.time_h > t0) & (self.data.alpha > 0.01) & (self.data.alpha < 0.95)
        t_delta = self.data.time_h[mask] - t0
        alpha = self.data.alpha[mask]
        dict_linear = {}

        if len(alpha) < 30:
            raise KineticsCalculationError("K-D 拟合有效 alpha 数据不足；请使用覆盖加速期和降速期的完整量热曲线。")

        a_peak = float(np.interp(t_peak, self.data.time_h, self.data.alpha))
        alpha_max = float(alpha.max())
        min_stage_points = 6

        m_ng = self._stage_mask(
            alpha=alpha,
            lower=0.02,
            upper=max(0.03, a_peak * 0.95),
            fallback_lower=0.02,
            fallback_upper=min(0.35, alpha_max * 0.55),
            center=max(0.04, a_peak * 0.50),
            min_points=min_stage_points,
            label="NG",
        )
        x_ng = np.log(t_delta[m_ng])
        y_ng = np.log(-np.log(1.0 - alpha[m_ng]))
        slope_ng, int_ng, r_val, _, _ = linregress(x_ng, y_ng)
        n = float(np.clip(slope_ng, 0.5, 5.0))
        k1 = float(np.clip(np.exp(int_ng / n), 1e-6, 1.0))
        r2_ng = float(r_val**2)
        dict_linear["[NG] X: ln(t-t0)"], dict_linear["[NG] Y: ln(-ln(1-α))"] = x_ng, y_ng

        a_i_start = max(a_peak, 0.05)
        a_i_end = min(a_peak + 0.18, alpha_max * 0.72)
        m_i = self._stage_mask(
            alpha=alpha,
            lower=a_i_start,
            upper=a_i_end,
            fallback_lower=max(0.06, alpha_max * 0.25),
            fallback_upper=max(0.12, alpha_max * 0.72),
            center=min(alpha_max * 0.55, max(a_peak, alpha_max * 0.40)),
            min_points=min_stage_points,
            label="I",
        )
        x_i = np.log(t_delta[m_i])
        y_i = np.log(1.0 - (1.0 - alpha[m_i]) ** (1.0 / 3.0))
        int_i = float(np.mean(y_i - x_i))
        k2 = float(np.clip(np.exp(int_i), 1e-7, 1.0))
        y_pred_i = x_i + int_i
        r2_i = self._safe_r2(y_i, y_pred_i)
        dict_linear["[I] X: ln(t-t0)"], dict_linear["[I] Y: ln(1-(1-α)^1/3)"] = x_i, y_i

        a_d_start = min(max(a_peak + 0.15, alpha_max * 0.55), alpha_max * 0.80)
        a_d_end = alpha_max * 0.93
        m_d = self._stage_mask(
            alpha=alpha,
            lower=a_d_start,
            upper=a_d_end,
            fallback_lower=max(0.10, alpha_max * 0.50),
            fallback_upper=alpha_max * 0.94,
            center=alpha_max * 0.78,
            min_points=min_stage_points,
            label="D",
        )
        x_d = np.log(t_delta[m_d])
        y_d = 2.0 * np.log(1.0 - (1.0 - alpha[m_d]) ** (1.0 / 3.0))
        int_d = float(np.mean(y_d - x_d))
        k3 = float(np.clip(np.exp(int_d), 1e-8, 1.0))
        y_pred_d = x_d + int_d
        r2_d = self._safe_r2(y_d, y_pred_d)
        dict_linear["[D] X: ln(t-t0)"], dict_linear["[D] Y: 2*ln(1-(1-α)^1/3)"] = x_d, y_d

        a1, a2 = self._find_boundaries(k1, n, k2, k3, a_peak)
        return k1, n, k2, k3, a1, a2, r2_ng, r2_i, r2_d, dict_linear
