from __future__ import annotations

from typing import Tuple

import numpy as np

from core.kinetics_solver import KDSolver as _BaseKDSolver
from utils.exceptions import KineticsCalculationError


class KDSolver(_BaseKDSolver):
    def _validate_input_data(self) -> None:
        super()._validate_input_data()

        cumulative = self.data.cumulative_heat_j_g
        drops = np.diff(cumulative)
        if not np.any(drops < 0):
            return

        span = max(float(np.ptp(cumulative)), 1.0)
        tolerance = max(1e-3, span * 1e-3)
        worst_drop = float(np.min(drops))
        if worst_drop < -tolerance:
            raise KineticsCalculationError(
                f"累计热量存在明显回落（单步最小 {worst_drop:.4g} J/g），请先做基线复核。"
            )

        # 小抖动别让 alpha 倒着走。
        self.data.cumulative_heat_j_g = np.maximum.accumulate(cumulative)
        self._add_warning("累计热量有轻微回落，已按单调包络处理。")

    def _calculate_qmax(
        self,
        t0: float,
        t_peak: float,
    ) -> Tuple[float, float, float, float, dict, bool, str, float]:
        values = list(super()._calculate_qmax(t0, t_peak))
        qmax, _, q_at_t0, _, _, _, qmax_method, _ = values

        if qmax_method == "knudsen_linear_extrapolation":
            return tuple(values)

        mask = self.data.time_h > t0
        times = self.data.time_h[mask] - t0
        heats = self.data.cumulative_heat_j_g[mask] - q_at_t0
        valid = np.isfinite(times) & np.isfinite(heats) & (heats >= 0)
        times = times[valid]
        heats = heats[valid]

        target = qmax / 2.0
        if len(heats) and target <= float(np.max(heats)):
            unique_heats, indices = np.unique(heats, return_index=True)
            values[1] = float(np.interp(target, unique_heats, times[indices]))

        return tuple(values)

    def _integral_domain_linear_fitting(self, t0: float, t_peak: float, qmax: float):
        values = list(super()._integral_domain_linear_fitting(t0, t_peak, qmax))
        k1, n, k2, k3 = values[:4]
        linear = values[-1]

        x_ng = linear["[NG] X: ln(t-t0)"]
        y_ng = linear["[NG] Y: ln(-ln(1-α))"]
        x_i = linear["[I] X: ln(t-t0)"]
        y_i = linear["[I] Y: ln(1-(1-α)^1/3)"]
        x_d = linear["[D] X: ln(t-t0)"]
        y_d = linear["[D] Y: 2*ln(1-(1-α)^1/3)"]

        values[6] = self._safe_r2(y_ng, n * x_ng + n * np.log(k1))
        values[7] = self._safe_r2(y_i, x_i + np.log(k2))
        values[8] = self._safe_r2(y_d, x_d + np.log(k3))
        return tuple(values)

    def execute_pipeline(self):
        result = super().execute_pipeline()
        result.induction_duration_h = max(0.0, result.t0_h - float(self.data.time_h[0]))
        return result
