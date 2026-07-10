from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from gui.main_window import MainWindow as _BaseMainWindow


class MainWindow(_BaseMainWindow):
    def _on_error(self, err_msg: str) -> None:
        self.control_panel.update_status("核心引擎执行异常", is_error=True)
        self.control_panel.btn_calc.setEnabled(True)
        self.control_panel.btn_load.setEnabled(True)
        self.control_panel.btn_extract.setEnabled(self.cached_hydration_data is not None)

        has_result = self.cached_params is not None
        self.control_panel.btn_export_excel.setEnabled(has_result)
        self.control_panel.btn_export_images.setEnabled(has_result)
        QMessageBox.critical(self, "计算失败", err_msg)
