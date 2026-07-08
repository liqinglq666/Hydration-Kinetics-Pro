from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.data_models import HydrationData
from core.data_parser import CalorimetryParser
from core.kinetics_solver import KDSolver
from utils.exceptions import DataParserError, KineticsCalculationError


def _synthetic_calorimetry_frame() -> pd.DataFrame:
    time_h = np.linspace(0.0, 96.0, 481)
    qmax = 280.0
    midpoint = 16.0
    width = 5.0
    cumulative = qmax / (1.0 + np.exp(-(time_h - midpoint) / width))
    cumulative = cumulative - cumulative[0]
    heat_flow = np.gradient(cumulative, time_h) / 3.6
    return pd.DataFrame(
        {
            "time_h": time_h,
            "heat_flow_mw_g": heat_flow,
            "cumulative_heat_j_g": cumulative,
        }
    )


def test_parser_respects_normalized_mode(tmp_path: Path) -> None:
    df = _synthetic_calorimetry_frame()
    csv_path = tmp_path / "normalized.csv"
    df.to_csv(csv_path, index=False)

    data = CalorimetryParser(sample_mass_g=5.0, input_mode="normalized").parse(csv_path)

    np.testing.assert_allclose(data.heat_flow_mw_g, df["heat_flow_mw_g"].to_numpy())
    np.testing.assert_allclose(data.cumulative_heat_j_g, df["cumulative_heat_j_g"].to_numpy())
    assert data.input_mode == "normalized"
    assert data.detected_unit_mode == "normalized"
    assert data.sample_mass_g == 5.0


def test_parser_respects_total_mode(tmp_path: Path) -> None:
    mass = 5.0
    df_norm = _synthetic_calorimetry_frame()
    df_total = pd.DataFrame(
        {
            "time_h": df_norm["time_h"],
            "heat_flow_mw": df_norm["heat_flow_mw_g"] * mass,
            "cumulative_heat_j": df_norm["cumulative_heat_j_g"] * mass,
        }
    )
    csv_path = tmp_path / "total.csv"
    df_total.to_csv(csv_path, index=False)

    data = CalorimetryParser(sample_mass_g=mass, input_mode="total").parse(csv_path)

    np.testing.assert_allclose(data.heat_flow_mw_g, df_norm["heat_flow_mw_g"].to_numpy())
    np.testing.assert_allclose(data.cumulative_heat_j_g, df_norm["cumulative_heat_j_g"].to_numpy())
    assert data.input_mode == "total"
    assert data.detected_unit_mode == "total"
    assert data.sample_mass_g == mass


def test_parser_rejects_unit_mode_mismatch(tmp_path: Path) -> None:
    df = _synthetic_calorimetry_frame()
    csv_path = tmp_path / "normalized.csv"
    df.to_csv(csv_path, index=False)

    with pytest.raises(DataParserError, match="表头单位与 GUI 选择不一致"):
        CalorimetryParser(sample_mass_g=5.0, input_mode="total").parse(csv_path)


def test_xls_is_explicitly_rejected(tmp_path: Path) -> None:
    xls_path = tmp_path / "legacy.xls"
    xls_path.write_text("not a real xls", encoding="utf-8")

    with pytest.raises(DataParserError, match="仅支持 .csv 和 .xlsx"):
        CalorimetryParser().parse(xls_path)


def test_solver_pipeline_on_96h_synthetic_data(tmp_path: Path) -> None:
    csv_path = tmp_path / "synthetic_96h.csv"
    _synthetic_calorimetry_frame().to_csv(csv_path, index=False)

    data = CalorimetryParser(sample_mass_g=1.0, input_mode="normalized").parse(csv_path)
    params = KDSolver(data, expected_peaks=1).execute_pipeline()

    assert params.qmax_j_g > 200.0
    assert params.t_peak_h > params.t0_h
    assert 0.0 < params.alpha_1 <= params.alpha_2 < 1.0
    assert params.origin_knudsen
    assert params.origin_kd_linear
    assert params.origin_rates
    assert params.input_mode == "normalized"
    assert params.detected_unit_mode == "normalized"
    assert params.t0_method == "auto_min_heat_flow"
    assert params.qmax_method in {"knudsen_linear_extrapolation", "fallback_q_final_x_1.15"}
    assert isinstance(params.qmax_fallback_used, bool)
    assert np.isfinite(params.r2_knudsen)
    assert isinstance(params.warnings, list)


def test_solver_accepts_manual_t0_and_manual_total_qmax(tmp_path: Path) -> None:
    df = _synthetic_calorimetry_frame()
    csv_path = tmp_path / "synthetic_manual.csv"
    df.to_csv(csv_path, index=False)

    data = CalorimetryParser(sample_mass_g=1.0, input_mode="normalized").parse(csv_path)
    manual_t0 = 2.0
    manual_qinf_total = float(df["cumulative_heat_j_g"].max() * 1.20)
    q_at_t0 = float(np.interp(manual_t0, data.time_h, data.cumulative_heat_j_g))

    params = KDSolver(
        data,
        expected_peaks=1,
        manual_t0_h=manual_t0,
        manual_qmax_total_j_g=manual_qinf_total,
        allow_qmax_fallback=False,
    ).execute_pipeline()

    assert params.t0_method == "manual"
    assert params.manual_t0_h == manual_t0
    assert params.qmax_method == "manual_total_cumulative_heat_qinf"
    assert params.qmax_fallback_used is False
    assert params.qmax_fallback_allowed is False
    assert params.manual_qmax_total_j_g == manual_qinf_total
    assert params.qmax_total_j_g == pytest.approx(manual_qinf_total)
    assert params.q_at_t0_j_g == pytest.approx(q_at_t0)
    assert params.qmax_j_g == pytest.approx(manual_qinf_total - q_at_t0)


def test_solver_rejects_invalid_manual_qmax(tmp_path: Path) -> None:
    df = _synthetic_calorimetry_frame()
    csv_path = tmp_path / "synthetic_bad_qmax.csv"
    df.to_csv(csv_path, index=False)

    data = CalorimetryParser(sample_mass_g=1.0, input_mode="normalized").parse(csv_path)
    bad_qinf_total = float(df["cumulative_heat_j_g"].max() * 0.80)

    with pytest.raises(KineticsCalculationError, match="手动 Q∞ 不足"):
        KDSolver(data, manual_t0_h=2.0, manual_qmax_total_j_g=bad_qinf_total).execute_pipeline()


def test_solver_fails_explicitly_on_short_data() -> None:
    data = HydrationData(
        time_h=np.array([0.0, 0.5, 1.0, 1.5]),
        heat_flow_mw_g=np.array([0.1, 0.2, 0.3, 0.2]),
        cumulative_heat_j_g=np.array([0.0, 0.2, 0.5, 0.7]),
    )

    with pytest.raises(KineticsCalculationError):
        KDSolver(data).execute_pipeline()
