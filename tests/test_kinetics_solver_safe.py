from __future__ import annotations

import numpy as np
import pytest

from core.data_models import HydrationData, KineticsParameters
from core.kinetics_solver import KDSolver as BaseKDSolver
from core.kinetics_solver_safe import KDSolver
from utils.exceptions import KineticsCalculationError


def make_data(cumulative: np.ndarray) -> HydrationData:
    time = np.arange(len(cumulative), dtype=float)
    return HydrationData(
        time_h=time,
        heat_flow_mw_g=np.ones_like(time),
        cumulative_heat_j_g=np.asarray(cumulative, dtype=float),
    )


def test_small_drop_uses_monotonic_envelope():
    cumulative = np.linspace(0.0, 20.0, 25)
    cumulative[12] = cumulative[11] - 0.001
    solver = KDSolver(make_data(cumulative))

    solver._validate_input_data()

    assert np.all(np.diff(solver.data.cumulative_heat_j_g) >= 0)


def test_large_drop_is_rejected():
    cumulative = np.linspace(0.0, 20.0, 25)
    cumulative[12] = cumulative[11] - 1.0
    solver = KDSolver(make_data(cumulative))

    with pytest.raises(KineticsCalculationError, match="明显回落"):
        solver._validate_input_data()


def test_fallback_t50_uses_interpolation(monkeypatch):
    data = HydrationData(
        time_h=np.array([0.0, 1.0, 2.0, 3.0]),
        heat_flow_mw_g=np.ones(4),
        cumulative_heat_j_g=np.array([0.0, 2.0, 6.0, 10.0]),
    )
    solver = KDSolver(data)

    monkeypatch.setattr(
        BaseKDSolver,
        "_calculate_qmax",
        lambda self, t0, t_peak: (10.0, 2.0, 0.0, 10.0, {}, True, "fallback_q_final_x_1.15", 0.9),
    )

    result = solver._calculate_qmax(0.0, 1.0)

    assert result[1] == pytest.approx(1.75)


def test_induction_duration_uses_real_start(monkeypatch):
    data = HydrationData(
        time_h=np.array([1.0, 2.0, 3.0]),
        heat_flow_mw_g=np.ones(3),
        cumulative_heat_j_g=np.array([0.0, 1.0, 2.0]),
    )
    params = KineticsParameters(
        t0_h=3.0,
        qmax_j_g=10.0,
        t50_h=1.0,
        n=1.0,
        k1=0.1,
        k2=0.1,
        k3=0.1,
        alpha_1=0.2,
        alpha_2=0.5,
    )
    monkeypatch.setattr(BaseKDSolver, "execute_pipeline", lambda self: params)

    result = KDSolver(data).execute_pipeline()

    assert result.induction_duration_h == pytest.approx(2.0)
