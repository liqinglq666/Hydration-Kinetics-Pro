from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import gui.main_window as main_window


class Button:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


class Canvas:
    def __init__(self):
        self.calls = []

    def plot_hydration_data(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def make_data(end):
    return SimpleNamespace(
        time_h=np.array([0.0, 1.0, 2.0]),
        heat_flow_mw_g=np.array([1.0, 2.0, 1.0]),
        cumulative_heat_j_g=np.array([0.0, float(end) / 2, float(end)]),
        parser_warnings=[],
    )


def make_window(monkeypatch):
    window = main_window.MainWindow.__new__(main_window.MainWindow)
    window.cached_hydration_data = None
    window.cached_params = None
    window._pending_hydration_data = None
    window.canvas = Canvas()
    displayed = []
    extracted = []
    window.results_panel = SimpleNamespace(
        display_results=lambda params: displayed.append(params),
        display_extracted_heat=lambda *args: extracted.append(args),
    )
    window.control_panel = SimpleNamespace(
        update_status=lambda *args, **kwargs: None,
        btn_calc=Button(),
        btn_load=Button(),
        btn_extract=Button(),
        btn_export_excel=Button(),
        btn_export_images=Button(),
    )
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *args, **kwargs: None)
    return window, displayed, extracted


def test_error_keeps_matching_last_valid_result(monkeypatch):
    window, _, _ = make_window(monkeypatch)
    old = make_data(10)
    new = make_data(20)
    params = object()
    window.cached_hydration_data = old
    window.cached_params = params

    window._on_data_loaded(new)
    assert window.cached_hydration_data is old
    assert window.cached_params is params
    assert window._pending_hydration_data is new

    window._on_error("calculation failed")
    assert window._pending_hydration_data is None
    assert window.cached_hydration_data is old
    assert window.cached_params is params
    assert window.canvas.calls[-1][0][2] is old.cumulative_heat_j_g
    assert window.canvas.calls[-1][1]["params"] is params
    assert window.control_panel.btn_export_excel.enabled is True
    assert window.control_panel.btn_export_images.enabled is True
    assert window.control_panel.btn_extract.enabled is True


def test_error_after_first_parse_allows_extraction_but_not_export(monkeypatch):
    window, _, _ = make_window(monkeypatch)
    parsed = make_data(20)
    window._on_data_loaded(parsed)
    window._on_error("calculation failed")

    assert window.cached_hydration_data is parsed
    assert window.cached_params is None
    assert window._pending_hydration_data is None
    assert window.control_panel.btn_extract.enabled is True
    assert window.control_panel.btn_export_excel.enabled is False
    assert window.control_panel.btn_export_images.enabled is False


def test_success_commits_data_and_parameters_together(monkeypatch):
    window, displayed, _ = make_window(monkeypatch)
    old = make_data(10)
    new = make_data(20)
    params = object()
    window.cached_hydration_data = old
    window.cached_params = object()

    window._on_data_loaded(new)
    window._on_finished((params, new))

    assert window.cached_hydration_data is new
    assert window.cached_params is params
    assert window._pending_hydration_data is None
    assert displayed == [params]
    assert window.control_panel.btn_export_excel.enabled is True


def test_extracts_from_pending_data_while_computing(monkeypatch):
    window, _, extracted = make_window(monkeypatch)
    window.cached_hydration_data = make_data(10)
    window._pending_hydration_data = make_data(20)

    window._handle_heat_extraction("1")
    assert len(extracted) == 1
    assert extracted[0][1].tolist() == [10.0]


def test_error_before_new_parse_retains_previous_result(monkeypatch):
    window, _, _ = make_window(monkeypatch)
    window.cached_hydration_data = make_data(10)
    window.cached_params = object()

    window._on_error("parser failed")
    assert window.cached_params is not None
    assert window.control_panel.btn_export_excel.enabled is True
    assert not window.canvas.calls
