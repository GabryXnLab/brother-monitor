#!/usr/bin/env python3
# brother_monitor.py
from __future__ import annotations
import sys
import os
import signal
import tempfile
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtCore import QTimer

from config import load_config, save_config
from drivers.base import PrinterData
from drivers.brother_http import BrotherHTTPDriver
from history import HistoryDB
from main_window import MainWindow
from tray import BrotherTray, LEVEL_WARN, LEVEL_CRIT

APP_NAME = "printer-monitor"
ORG_NAME = "printer-monitor"


def _make_driver(printer_cfg):
    if printer_cfg.driver == "brother_http":
        return BrotherHTTPDriver(base_url=printer_cfg.url)
    if printer_cfg.driver == "snmp":
        from drivers.snmp import SNMPDriver
        return SNMPDriver(host=printer_cfg.host, community=printer_cfg.community)
    raise ValueError(f"Unknown driver: {printer_cfg.driver!r}")


def _check_notifications(tray: BrotherTray, data: PrinterData,
                          printer_cfg, printer_name: str) -> None:
    n = printer_cfg.notifications
    if not n.enabled:
        return
    if data.status == "offline":
        tray.notify(f"{printer_name}:offline",
                    f"{printer_name} — offline",
                    "La stampante non è raggiungibile.", LEVEL_CRIT)
    elif data.status == "error":
        tray.notify(f"{printer_name}:error",
                    f"{printer_name} — errore",
                    f"Errore: {data.status_detail or 'sconosciuto'}", LEVEL_CRIT)
    if data.status not in ("offline", "error"):
        if data.toner_pct < n.toner_threshold:
            tray.notify(f"{printer_name}:toner",
                        f"{printer_name} — toner in esaurimento",
                        f"Toner al {data.toner_pct}% — considera la sostituzione.",
                        LEVEL_WARN)
        if data.drum_pct < n.drum_threshold:
            tray.notify(f"{printer_name}:drum",
                        f"{printer_name} — tamburo in esaurimento",
                        f"Tamburo all'{data.drum_pct}% — considera la sostituzione.",
                        LEVEL_WARN)


def _enforce_single_instance() -> None:
    """Termina un'eventuale istanza precedente e registra il PID corrente."""
    lock_path = os.path.join(tempfile.gettempdir(),
                             f"printer-monitor-{os.getuid()}.pid")
    if os.path.exists(lock_path):
        try:
            with open(lock_path, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError, FileNotFoundError):
            pass  # processo già terminato o PID non valido

    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))


def main() -> None:
    _enforce_single_instance()
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)

    cfg     = load_config()
    history_db = HistoryDB()
    drivers = [_make_driver(p) for p in cfg.printers]

    # data_cache holds the latest PrinterData per printer index
    data_cache: list[PrinterData] = [PrinterData() for _ in cfg.printers]

    window = MainWindow(cfg)
    tray   = BrotherTray(window)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "ATTENZIONE: nessun system tray disponibile (nessuno "
            "StatusNotifierWatcher sul bus DBus). Su GNOME serve l'estensione "
            "'AppIndicator and KStatusNotifierItem Support' "
            "(dnf install gnome-shell-extension-appindicator, poi abilitala "
            "con 'gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com' "
            "e rifai il login). L'app continua ad avviarsi ma l'icona non sarà visibile.",
            file=sys.stderr,
        )
    tray.show()

    def do_refresh(idx: int) -> None:
        data = drivers[idx].fetch()
        ts   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data_cache[idx] = data
        printer_cfg = cfg.printers[idx]
        history_db.record(printer_cfg.name, data)
        # Update UI only if this printer is currently selected
        if window.selected_printer_index() == idx:
            window.update_data(data, ts)
            window.update_history(
                history_db.get_recent(printer_cfg.name, limit=200))
        tray.update_all_statuses(data_cache, cfg.printers)
        _check_notifications(tray, data, printer_cfg, printer_cfg.name)

    timers: list[QTimer] = []
    for i, printer_cfg in enumerate(cfg.printers):
        t = QTimer()
        t.timeout.connect(lambda _i=i: do_refresh(_i))
        t.start(printer_cfg.polling_interval_sec * 1000)
        timers.append(t)

    def refresh_selected():
        do_refresh(window.selected_printer_index())

    window.refresh_requested.connect(refresh_selected)
    tray._act_refresh.triggered.connect(refresh_selected)

    window.refresh_interval_changed.connect(
        lambda secs: timers[window.selected_printer_index()].setInterval(secs * 1000))

    window.config_saved.connect(lambda new_cfg: save_config(new_cfg))

    window.printer_selected.connect(
        lambda idx: (
            window.update_data(
                data_cache[idx],
                "—" if data_cache[idx].status == "offline" else
                datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            ),
            window.update_history(
                history_db.get_recent(cfg.printers[idx].name, limit=200)
            )
        )
    )

    window.clear_history_requested.connect(
        lambda: history_db.clear(
            cfg.printers[window.selected_printer_index()].name))

    # Initial fetch for all printers
    for i in range(len(cfg.printers)):
        do_refresh(i)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
