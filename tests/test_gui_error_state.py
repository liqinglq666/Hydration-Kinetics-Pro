from __future__ import annotations

from types import SimpleNamespace

import gui.main_window_safe as safe_window


class Button:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


def test_error_keeps_last_valid_exports(monkeypatch):
    window = safe_window.MainWindow.__new__(safe_window.MainWindow)
    window.cached_hydration_data = object()
    window.cached_params = object()
    window.control_panel = SimpleNamespace(
        update_status=lambda *args, **kwargs: None,
        btn_calc=Button(),
        btn_load=Button(),
        btn_extract=Button(),
        btn_export_excel=Button(),
        btn_export_images=Button(),
    )
    monkeypatch.setattr(safe_window.QMessageBox, "critical", lambda *args, **kwargs: None)

    window._on_error("boom")

    assert window.control_panel.btn_export_excel.enabled is True
    assert window.control_panel.btn_export_images.enabled is True
    assert window.control_panel.btn_extract.enabled is True
