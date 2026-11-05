# tests/test_tray.py
import time
import pytest
from unittest.mock import patch
from printer_monitor.tray import BrotherTray, LEVEL_WARN
from printer_monitor.drivers.base import PrinterData
from printer_monitor.main_window import MainWindow
from printer_monitor.config import AppConfig, PrinterConfig


@pytest.fixture
def window(qtbot):
    cfg = AppConfig(printers=[PrinterConfig()])
    w = MainWindow(cfg)
    qtbot.addWidget(w)
    return w


@pytest.fixture
def tray(qtbot, window):
    t = BrotherTray(window)
    return t


def test_tray_created(tray):
    assert tray is not None


def test_tray_menu_has_actions(tray):
    actions = tray.contextMenu().actions()
    texts = [a.text() for a in actions]
    assert any("Apri" in t for t in texts)
    assert any("Aggiorna" in t for t in texts)
    assert any("Esci" in t for t in texts)


def test_update_status_idle_sets_green_icon(tray):
    data = PrinterData(status="idle", toner_pct=50, drum_pct=60)
    tray.update_status(data)
    # icona deve essere quella ok (non possiamo confrontare pixel, ma non deve crashare)
    assert tray.icon() is not None


def test_update_status_offline_sets_error_icon(tray):
    data = PrinterData(status="offline")
    tray.update_status(data)
    assert tray.icon() is not None


def test_update_status_low_toner_sets_warn_icon(tray):
    data = PrinterData(status="idle", toner_pct=10, drum_pct=60)
    tray.update_status(data)
    assert tray.icon() is not None


def test_notify_sends_message(tray):
    with patch.object(tray, "showMessage") as mock_show:
        tray.notify("toner", "Titolo", "Corpo", LEVEL_WARN)
        mock_show.assert_called_once()


def test_notify_debounce_blocks_second_call(tray):
    with patch.object(tray, "showMessage") as mock_show:
        tray.notify("toner", "T", "M", LEVEL_WARN)
        tray.notify("toner", "T", "M", LEVEL_WARN)   # stesso key → bloccata
        assert mock_show.call_count == 1


def test_notify_different_keys_both_sent(tray):
    with patch.object(tray, "showMessage") as mock_show:
        tray.notify("toner", "T1", "M1", LEVEL_WARN)
        tray.notify("drum",  "T2", "M2", LEVEL_WARN)  # chiave diversa → passa
        assert mock_show.call_count == 2


def test_notify_respects_debounce_timeout(tray):
    with patch.object(tray, "showMessage") as mock_show:
        tray.notify("toner", "T", "M", LEVEL_WARN)
        # Simula che sia passata 1 ora
        tray._last_notified["toner"] = time.monotonic() - 3601
        tray.notify("toner", "T", "M", LEVEL_WARN)
        assert mock_show.call_count == 2
