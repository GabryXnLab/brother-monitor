# tests/test_main_window.py
import pytest
from PyQt6.QtWidgets import QTabWidget
from printer_monitor.config import AppConfig, PrinterConfig
from printer_monitor.main_window import MainWindow
from printer_monitor.drivers.base import PrinterData


@pytest.fixture
def printer_cfg():
    return PrinterConfig()


@pytest.fixture
def cfg(printer_cfg):
    return AppConfig(printers=[printer_cfg])


@pytest.fixture
def window(qtbot, cfg):
    w = MainWindow(cfg)
    qtbot.addWidget(w)
    return w


def test_window_has_four_tabs(window):
    tabs = window.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 4


def test_window_tab_names(window):
    tabs = window.findChild(QTabWidget)
    assert tabs.tabText(0) == "Stato"
    assert tabs.tabText(1) == "Statistiche"
    assert tabs.tabText(2) == "Storico"
    assert tabs.tabText(3) == "Impostazioni"


def test_update_data_status_idle(window):
    data = PrinterData(
        status="idle",
        toner_pct=40,
        drum_pct=88,
        model="Brother DCP-L2550DN series",
        serial="E78283F1N254602",
        page_count=1472,
        avg_coverage=8.26,
        jams={"total": 2, "tray1": 1, "inside": 1},
        replace_counts={"toner": 1, "drum": 0},
        errors=[{"desc": "Incepp. interno", "page": 1109}],
    )
    window.update_data(data, "01/04/2026 21:00:00")
    assert window.gauge_toner._value == 40
    assert window.gauge_drum._value == 88
    assert "DCP-L2550DN" in window.lbl_model.text()
    assert "E78283F1N254602" in window.lbl_serial.text()
    assert "Pronto" in window.lbl_status.text()


def test_update_data_status_offline(window):
    data = PrinterData(status="offline")
    window.update_data(data, "01/04/2026 21:00:00")
    assert "raggiungibile" in window.lbl_status.text().lower() or \
           "offline" in window.lbl_status.text().lower()


def test_update_data_stats_tab(window):
    data = PrinterData(
        page_count=1472,
        avg_coverage=8.26,
        jams={"total": 2, "tray1": 1, "inside": 1, "rear": 0},
        replace_counts={"toner": 1, "drum": 0},
        errors=[{"desc": "Err1", "page": 100}, {"desc": "Err2", "page": 200}],
    )
    window.update_data(data, "—")
    assert "1472" in window.lbl_pages_total.text()
    assert "8.26" in window.lbl_coverage.text()
    assert window.tbl_errors.rowCount() == 2


def test_close_hides_window_not_quit(window, qtbot):
    window.show()
    assert window.isVisible()
    window.close()
    assert not window.isVisible()
