from __future__ import annotations

import pandas as pd
import pytest

from core.data_parser import CalorimetryParser
from utils.exceptions import DataParserError


def test_normalized_headers_cannot_run_as_total(tmp_path):
    path = tmp_path / "normalized.csv"
    pd.DataFrame(
        {
            "time_h": [0.0, 1.0, 2.0],
            "heat_flow_mW/g": [0.0, 1.0, 0.5],
            "cumulative_heat_J/g": [0.0, 2.0, 4.0],
        }
    ).to_csv(path, index=False)

    with pytest.raises(DataParserError, match="单位与 GUI 选择冲突"):
        CalorimetryParser(sample_mass_g=5.0, input_mode="total").parse(path)


def test_matching_normalized_mode_is_not_divided_by_mass(tmp_path):
    path = tmp_path / "normalized.csv"
    pd.DataFrame(
        {
            "time_h": [0.0, 1.0, 2.0],
            "heat_flow_mW/g": [0.0, 1.0, 0.5],
            "cumulative_heat_J/g": [0.0, 2.0, 4.0],
        }
    ).to_csv(path, index=False)

    data = CalorimetryParser(sample_mass_g=5.0, input_mode="normalized").parse(path)

    assert data.heat_flow_mw_g.tolist() == [0.0, 1.0, 0.5]
    assert data.cumulative_heat_j_g.tolist() == [0.0, 2.0, 4.0]
