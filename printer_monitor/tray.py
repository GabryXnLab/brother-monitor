# printer_monitor/tray.py
from __future__ import annotations
import time
import os

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt

from printer_monitor.drivers.base import PrinterData

# UNUSED: verifica se eliminabile invece di cancellarla
LEVEL_INFO = QSystemTrayIcon.MessageIcon.Information

LEVEL_WARN = QSystemTrayIcon.MessageIcon.Warning
LEVEL_CRIT = QSystemTrayIcon.MessageIcon.Critical


def _make_icon(color: str) -> QIcon:
    """Genera un'icona SVG del colore dato usando il file esterno."""
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Printer--Streamline-Plump.svg")
    try:
        with open(icon_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
    except Exception:
        # Fallback all'icona circolare se il file non è trovato o c'è un errore
        px = QPixmap(22, 22)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 18, 18)
        p.end()
        return QIcon(px)

    svg_content = svg_content.replace("#000000", color)
    px = QPixmap()
    px.loadFromData(svg_content.encode("utf-8"))
    return QIcon(px)


class BrotherTray(QSystemTrayIcon):
    DEBOUNCE_SECS = 3600  # 60 minuti

    def __init__(self, window, parent=None):
        # Le icone vengono create qui, dopo che QApplication esiste
        self._icon_ok   = _make_icon("#4caf50")
        self._icon_warn = _make_icon("#ff9800")
        self._icon_err  = _make_icon("#f44336")

        super().__init__(self._icon_ok, parent)
        self.window = window
        self._last_notified: dict[str, float] = {}

        menu = QMenu()
        self._act_open    = menu.addAction("Apri Monitor Brother")
        self._act_status  = menu.addAction("Stato: —")
        self._act_status.setEnabled(False)
        menu.addSeparator()
        self._act_refresh = menu.addAction("Aggiorna ora")  # wired by caller
        menu.addSeparator()
        menu.addAction("Esci").triggered.connect(QApplication.quit)
        self.setContextMenu(menu)

        self._act_open.triggered.connect(self._show_window)
        self.activated.connect(self._on_activated)
        self.setToolTip("Brother Monitor — DCP-L2550DN")

    # ------------------------------------------------------------------ #

    def _show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self._show_window()

    # ------------------------------------------------------------------ #

    # UNUSED: verifica se eliminabile invece di cancellarla
    def update_status(self, data: PrinterData, printer_name: str = "") -> None:
        label = {"idle": "Pronto", "sleep": "Risparmio",
                 "printing": "Stampa in corso...",
                 "error": "Errore", "offline": "Offline"}
        display = printer_name or "Stampante"
        self._act_status.setText(f"{display}: {label.get(data.status, data.status)}")

        if data.status in ("error", "offline"):
            self.setIcon(self._icon_err)
        elif (data.toner_pct < 15) or (data.drum_pct < 10):
            self.setIcon(self._icon_warn)
        else:
            self.setIcon(self._icon_ok)

        self.setToolTip(
            f"{display}  •  Toner: {data.toner_pct}%  •  Tamburo: {data.drum_pct}%"
        )

    def update_all_statuses(self, data_list: list, printer_cfgs: list) -> None:
        """Update tray icon (worst state) and per-printer menu items."""
        # Update or create per-printer status actions
        if not hasattr(self, "_printer_actions"):
            self._printer_actions: list = []
            menu = self.contextMenu()
            # Insert per-printer items before the existing _act_status
            for _ in printer_cfgs:
                act = menu.addAction("")
                menu.insertAction(self._act_status, act)
                act.setEnabled(False)
                self._printer_actions.append(act)
            self._act_status.setVisible(False)  # hide the old single-printer item

        _label = {"idle": "Pronto", "sleep": "Risparmio",
                  "printing": "Stampa...", "error": "Errore", "offline": "Offline"}

        worst = "idle"
        _priority = {"error": 3, "offline": 3, "printing": 2, "sleep": 1, "idle": 0}

        for i, (data, cfg) in enumerate(zip(data_list, printer_cfgs)):
            if i < len(self._printer_actions):
                status_str = _label.get(data.status, data.status)
                self._printer_actions[i].setText(
                    f"● {cfg.name}  {status_str}  "
                    f"T:{data.toner_pct}%  D:{data.drum_pct}%")
            if _priority.get(data.status, 0) > _priority.get(worst, 0):
                worst = data.status

        if worst in ("error", "offline"):
            self.setIcon(self._icon_err)
        elif any((d.toner_pct < 15 or d.drum_pct < 10) for d in data_list):
            self.setIcon(self._icon_warn)
        else:
            self.setIcon(self._icon_ok)

        # Build combined tooltip
        lines = [f"{c.name}: T:{d.toner_pct}% D:{d.drum_pct}%"
                 for d, c in zip(data_list, printer_cfgs)]
        self.setToolTip("\n".join(lines))

    def notify(self, key: str, title: str, message: str,
               level: QSystemTrayIcon.MessageIcon = LEVEL_WARN) -> None:
        now = time.monotonic()
        if now - self._last_notified.get(key, float("-inf")) < self.DEBOUNCE_SECS:
            return
        self._last_notified[key] = now
        self.showMessage(title, message, level, 6000)
