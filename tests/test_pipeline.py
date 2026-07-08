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


def test_solver_fails_explicitly_on_short_data() -> None:
    data = HydrationData(
        time_h=np.array([0.0, 0.5, 1.0, 1.5]),
        heat_flow_mw_g=np.array([0.1, 0.2, 0.3, 0.2]),
        cumulative_heat_j_g=np.array([0.0, 0.2, 0.5, 0.7]),
    )

    with pytest.raises(KineticsCalculationError):
        KDSolver(data).execute_pipeline()
