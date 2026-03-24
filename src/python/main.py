import sys
import os
import csv
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTableWidgetItem, QSplashScreen
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui.mainWindow import Ui_MainWindow
from ui.subUi import NoImgWarning, ProcessingDialog
from ui.about import AboutDialog
import core.io as io
from core import fibre_measure
from core import pore_measure
from core.render import fibre_result_visualise, pore_result_visualise


# Default parameter values — used when data.json is missing keys
DEFAULTS = {
    "jer": 40,
    "scale_factor": 1.25,
    "rate": 0.5,
    "msd": 50,
    "sigma": 2.0,
    "threshold": 0.15,
    "img_path": "",
    "mode": "f",
}


def _load_json(json_file: str) -> dict:
    with open(json_file, "r") as f:
        return json.load(f)


def _save_json(json_file: str, data: dict) -> None:
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)


def _ensure_defaults() -> None:
    """Make sure data.json contains all required keys with default values."""
    data = _load_json("config.json")
    changed = False
    for key, val in DEFAULTS.items():
        if key not in data:
            data[key] = val
            changed = True
    if changed:
        _save_json("config.json", data)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon("icon.ico"))
        self.setWindowTitle("FibreScope")

        _ensure_defaults()
        self._canvaSet()
        self._connectSignals()
        self._loadSidebarFromJson()

        data = _load_json("config.json")
        self.mode = data["mode"]
        data["img_path"] = ""
        _save_json("config.json", data)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connectSignals(self):
        self.ui.actionOpen_Image.triggered.connect(io.selectImg)
        self.ui.actionExit.triggered.connect(self._closeWindow)
        self.ui.actionFibre_Measure.triggered.connect(self._toggleFibreMode)
        self.ui.actionPore_Measure.triggered.connect(self._togglePoreMode)
        self.ui.actionRun_Analysis.triggered.connect(self._start_analysis)
        self.ui.actionSave_Result.triggered.connect(self._save_result)
        self.ui.actionAbout.triggered.connect(self._about)
        self.ui.set_button.clicked.connect(self._setSidebarParams)

    # ------------------------------------------------------------------
    # Sidebar: load from JSON → populate inputs
    # ------------------------------------------------------------------
    def _loadSidebarFromJson(self):
        data = _load_json("config.json")
        # Show current values as placeholder text so the field looks populated
        # even if the user hasn't typed anything yet.
        self.ui.jer_input.setText(str(data["jer"]))
        self.ui.scale_input.setText(str(data["scale_factor"]))
        self.ui.rate_input.setText(str(data["rate"]))
        self.ui.msd_input.setText(str(data["msd"]))
        self.ui.smoothing_input.setText(str(data["smoothing"]))
        self.ui.threshold_input.setText(str(data["threshold"]))
        self.ui.oer_input.setText(str(data["oer"]))

    # ------------------------------------------------------------------
    # Sidebar: validate inputs → write to JSON
    # ------------------------------------------------------------------
    def _setSidebarParams(self):
        fields = {
            "jer": (self.ui.jer_input,         float, 1,    500),
            "scale_factor": (self.ui.scale_input,       float, 0.01, 100),
            "rate": (self.ui.rate_input,        float, 0.01, 1.0),
            "msd": (self.ui.msd_input,         int,   5,    500),
            "sigma": (self.ui.smoothing_input,   float, 0.5,  10),
            "threshold": (self.ui.threshold_input,   float, 0.01, 1.0),
            "oer": (self.ui.oer_input,   float, 1, 500)
        }

        data = _load_json("config.json")
        errors = []

        for key, (widget, cast, lo, hi) in fields.items():
            text = widget.text().strip()
            if text == "":
                # Empty → keep current value, no update needed
                continue
            try:
                val = cast(text)
                if not (lo <= val <= hi):
                    raise ValueError(f"out of range [{lo}, {hi}]")
                data[key] = val
            except ValueError as e:
                errors.append(f"{key}: {e}")
                widget.setStyleSheet("border: 1px solid red;")
                continue
            widget.setStyleSheet("")  # Clear error highlight

        if errors:
            # Report but still save whatever was valid
            print("Parameter warnings:", errors)
        else:
            _save_json("config.json", data)
            self._loadSidebarFromJson()   # Refresh displayed values
            print("Parameters saved:", {k: data[k] for k in fields})

        _save_json("config.json", data)

    # ------------------------------------------------------------------
    # Mode toggles
    # ------------------------------------------------------------------
    def _toggleFibreMode(self):
        data = _load_json("config.json")
        data["mode"] = "f"
        _save_json("config.json", data)
        self.setWindowTitle("FibreScope - fibre mode")

    def _togglePoreMode(self):
        data = _load_json("config.json")
        data["mode"] = "p"
        _save_json("config.json", data)
        self.setWindowTitle("FibreScope - pore mode")

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------
    def _canvaSet(self):
        # Detect system theme via window background colour
        palette = self.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        is_dark = bg_color.lightness() < 128

        if is_dark:
            plt.style.use('dark_background')
            fig_facecolor = '#2b2b2b'
        else:
            plt.style.use('default')
            fig_facecolor = '#f5f5f5'

        self.fig = Figure(facecolor=fig_facecolor)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background-color: {fig_facecolor};")

        layout = self.ui.resultFrame.layout()
        if layout is None:
            layout = QVBoxLayout(self.ui.resultFrame)
            self.ui.resultFrame.setLayout(layout)
        layout.addWidget(self.canvas)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def _start_analysis(self):
        self.processing = ProcessingDialog(self)
        self.processing.show()
        QApplication.processEvents()
        self.worker = AnalysisWorker(self)
        self.worker.resultReady.connect(self._render_results)
        self.worker.finished.connect(self._finish_analysis)
        self.worker.start()

    def _finish_analysis(self):
        self.processing.close()
        self.worker.deleteLater()

    def _compute_analysis(self):
        data = _load_json("config.json")
        img_path = data["img_path"]
        mode = data["mode"]
        self.fig.clear()

        if img_path == "":
            NoImgWarning(parent=self).exec()
            return None

        if mode == "f":
            return fibre_measure.measure(
                img_path,
                sample_rate=data["rate"],
                max_search_distance=int(data["msd"]),
                min_distance_hard=5,
                jer=data["jer"],
                sigma=data["sigma"],
                scale_factor=data["scale_factor"],
                threshold=data["threshold"],
                overlap_exclusion_radius=data["oer"]
            )

        if mode == "p":
            return pore_measure.measure(
                img_path,
                scale_factor=data["scale_factor"]
            )

        return None

    def _render_results(self, result):
        if result is None:
            NoImgWarning(parent=self).exec()
            return

        self.fig.clear()
        data = _load_json("config.json")

        if data["mode"] == "f":
            true_diameters, pairs, edge_mask, fibre_dict = result
            self._last_pairs = pairs   
            fibre_result_visualise(
                true_diameters,
                data["img_path"],
                pairs,
                edge_mask,
                fig=self.fig,
            )
            result_data = _load_json("data.json")
            result_data["Fibre Param"] = fibre_dict
            _save_json("data.json", result_data)
        else:
            area_arr, circularity_arr, solidity_arr, measured_contour, pore_dict = result
            pore_result_visualise(
                area_arr, circularity_arr, solidity_arr, measured_contour, fig=self.fig
            )
            result_data = _load_json("data.json")
            result_data["Pores Param"] = pore_dict
            _save_json("data.json", result_data)

        self.canvas.draw()
        self._show_result()

    def _show_result(self):
        config = _load_json("config.json")
        data = _load_json("data.json")
        mode_key = "Fibre Param" if config["mode"] == "f" else "Pores Param"
        p = data[mode_key]

        def item(val):
            i = QTableWidgetItem(str(round(val, 4)))
            i.setTextAlignment(Qt.AlignCenter)  # type: ignore
            return i

        q1, q3 = round(p["Q1, Q3"][0], 4), round(p["Q1, Q3"][1], 4)
        ci_lo, ci_hi = round(p["95% CI"][0], 4), round(p["95% CI"][1], 4)

        q1q3_item = QTableWidgetItem(f"{q1}, {q3}")
        q1q3_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
        ci_item = QTableWidgetItem(f"{ci_lo}, {ci_hi}")
        ci_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
        jer_item = QTableWidgetItem(str(round(config["jer"])))
        jer_item.setTextAlignment(Qt.AlignCenter)  # type: ignore

        self.ui.tableWidget.setItem(0, 0, item(p["Average"]))
        self.ui.tableWidget.setItem(0, 1, item(p["Standard Deviation"]))
        self.ui.tableWidget.setItem(0, 2, item(p["KDE Peak"]))
        self.ui.tableWidget.setItem(0, 3, item(p["SEM"]))
        self.ui.tableWidget.setItem(0, 4, item(p["median"]))
        self.ui.tableWidget.setItem(0, 5, q1q3_item)
        self.ui.tableWidget.setItem(0, 6, item(p["IQR"]))
        self.ui.tableWidget.setItem(0, 7, ci_item)
        self.ui.tableWidget.setItem(0, 8, jer_item)

    # ------------------------------------------------------------------
    # Save / About / Close
    # ------------------------------------------------------------------
    def _save_result(self):
        config = _load_json("config.json")
        mode_key = "Fibre Param" if config["mode"] == "f" else "Pores Param"

        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        folder = Path(timestamp)
        folder.mkdir(exist_ok=True)

        # Save result image
        self.fig.savefig(folder / f"{timestamp}.png")
        if config["mode"] == "f" and hasattr(self, '_last_pairs'):
            from core.render import save_measurement_overlay
            save_measurement_overlay(
                config["img_path"],
                self._last_pairs,
                str(folder / f"{timestamp}_overlay.png")
            )

        # Save Raw data as CSV
        try:
            result_data = _load_json("data.json")
            raw = result_data[mode_key]["Raw"]
            col_name = "diameter_px" if config["mode"] == "f" else "area_px"
            with open(folder / f"{timestamp}_raw.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([col_name])
                writer.writerows([[v] for v in raw])
        except (KeyError, FileNotFoundError) as e:
            print(f"CSV export skipped: {e}")

        print(f"Result saved to: {folder}/")

    def _about(self):
        AboutDialog(parent=self).exec()

    def _closeWindow(self):
        data = _load_json("config.json")
        data["img_path"] = ""
        _save_json("config.json", data)
        QApplication.quit()


# ----------------------------------------------------------------------
# Worker thread
# ----------------------------------------------------------------------
class AnalysisWorker(QThread):
    resultReady = Signal(object)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def run(self):
        import time
        time1 = time.time()
        result = self.main_window._compute_analysis()
        time2 = time.time()
        print(time2 - time1)
        self.resultReady.emit(result)


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    # splash = QSplashScreen(
    #     QPixmap("src/python/media/Splash2.png"),
    #     Qt.WindowStaysOnTopHint,  # type: ignore
    # )
    # splash.show()
    app.processEvents()
    window = MainWindow()
    window.show()
    # splash.finish(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
