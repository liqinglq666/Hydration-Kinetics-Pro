from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.data_models import HydrationData
from core.data_parser import CalorimetryParser
from core.kinetics_solver import KDSolver
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
    assert any("单调包络" in msg for msg in solver.warnings)


def test_large_drop_is_rejected():
    cumulative = np.linspace(0.0, 20.0, 25)
    cumulative[12] = cumulative[11] - 1.0
    solver = KDSolver(make_data(cumulative))

    with pytest.raises(KineticsCalculationError, match="明显回落"):
        solver._validate_input_data()


def test_manual_qmax_t50_uses_interpolation():
    data = make_data(np.linspace(0.0, 8.0, 96))
    solver = KDSolver(data, manual_qmax_total_j_g=10.0)

    qmax, t50, *_ = solver._calculate_qmax(t0=0.0, t_peak=10.0)

    assert qmax == pytest.approx(10.0)
    assert t50 == pytest.approx(59.375)


def test_induction_duration_uses_actual_record_start(monkeypatch):
    times = np.arange(3.0, 99.0)
    data = HydrationData(
        time_h=times,
        heat_flow_mw_g=np.ones_like(times),
        cumulative_heat_j_g=np.linspace(0.0, 8.0, len(times)),
        alpha=np.linspace(0.0, 0.8, len(times)),
    )
    monkeypatch.setattr(KDSolver, "_detect_t0", lambda self: 6.0)
    monkeypatch.setattr(KDSolver, "_detect_main_peak", lambda self, t0: 12.0)
    monkeypatch.setattr(KDSolver, "_extract_all_peaks", lambda self: [])
    monkeypatch.setattr(
        KDSolver,
        "_calculate_qmax",
        lambda self, t0, t_peak: (10.0, 5.0, 1.0, 11.0, {}, False, "manual_total_cumulative_heat_qinf", np.nan),
    )
    monkeypatch.setattr(
        KDSolver,
        "_integral_domain_linear_fitting",
        lambda self, t0, t_peak, qmax: (0.1, 1.0, 0.1, 0.1, 0.2, 0.5, 0.9, 0.9, 0.9, {}),
    )

    params = KDSolver(data).execute_pipeline()
    assert params.t0_h == pytest.approx(6.0)
    assert params.induction_duration_h == pytest.approx(3.0)


def test_r2_uses_final_constrained_parameters():
    time = np.arange(121, dtype=float)
    data = HydrationData(
        time_h=time,
        heat_flow_mw_g=np.ones_like(time),
        cumulative_heat_j_g=np.linspace(0.0, 10.0, len(time)),
        alpha=0.9 * (1.0 - np.exp(-time / 30.0)),
    )
    solver = KDSolver(data)
    k1, n, k2, k3, _, _, r2_ng, r2_i, r2_d, linear = solver._integral_domain_linear_fitting(
        t0=0.0, t_peak=15.0, qmax=20.0
    )

    x_ng = linear["[NG] X: ln(t-t0)"]
    y_ng = linear["[NG] Y: ln(-ln(1-α))"]
    x_i = linear["[I] X: ln(t-t0)"]
    y_i = linear["[I] Y: ln(1-(1-α)^1/3)"]
    x_d = linear["[D] X: ln(t-t0)"]
    y_d = linear["[D] Y: 2*ln(1-(1-α)^1/3)"]

    assert r2_ng == pytest.approx(solver._safe_r2(y_ng, n * x_ng + n * np.log(k1)))
    assert r2_i == pytest.approx(solver._safe_r2(y_i, x_i + np.log(k2)))
    assert r2_d == pytest.approx(solver._safe_r2(y_d, x_d + np.log(k3)))


def test_sample_pipeline_produces_valid_parameters():
    sample = Path(__file__).resolve().parents[1] / "examples" / "sample_96h_calorimetry_normalized.csv"
    data = CalorimetryParser(sample_mass_g=1.0, input_mode="normalized").parse(sample)
    params = KDSolver(data).execute_pipeline()

    assert params.t0_h >= data.time_h[0]
    assert params.qmax_j_g > 0
    assert np.isfinite([params.n, params.k1, params.k2, params.k3]).all()
    assert params.induction_duration_h == pytest.approx(params.t0_h - data.time_h[0])
