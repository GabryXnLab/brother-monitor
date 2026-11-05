# printer_monitor/main_window.py
from __future__ import annotations
import subprocess
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QSlider,
    QCheckBox, QComboBox, QGroupBox, QFormLayout, QHeaderView,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from printer_monitor.config import AppConfig
from printer_monitor.drivers.base import PrinterData
from printer_monitor.widgets import CircularGauge

AUTOSTART_PATH = Path.home() / ".config/autostart/printer-monitor.desktop"

_STATUS_COLOR = {
    "idle":     "#4caf50",
    "sleep":    "#2196f3",
    "printing": "#ff9800",
    "error":    "#f44336",
    "offline":  "#9e9e9e",
}
_STATUS_LABEL = {
    "idle":     "Pronto",
    "sleep":    "Risparmio energetico",
    "printing": "Stampa in corso",
    "error":    "Errore",
    "offline":  "Non raggiungibile",
}


class MainWindow(QMainWindow):
    refresh_requested = pyqtSignal()
    refresh_interval_changed = pyqtSignal(int)
    config_saved = pyqtSignal(AppConfig)
    clear_history_requested = pyqtSignal()
    printer_selected = pyqtSignal(int)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._printer_cfg = cfg.printers[0]
        self.setWindowTitle("Printer Monitor")
        self.setMinimumSize(520, 560)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Printer selector (visible only when more than 1 printer)
        if len(cfg.printers) > 1:
            selector_bar = QWidget()
            selector_bar.setStyleSheet("background: #f5f5f5; border-bottom: 1px solid #ddd;")
            sl = QHBoxLayout(selector_bar)
            sl.setContentsMargins(12, 6, 12, 6)
            sl.addWidget(QLabel("Stampante:"))
            self._combo_printers = QComboBox()
            for p in cfg.printers:
                self._combo_printers.addItem(p.name)
            self._combo_printers.currentIndexChanged.connect(self._on_printer_changed)
            sl.addWidget(self._combo_printers)
            sl.addStretch()
            root.addWidget(selector_bar)

        tabs = QTabWidget()
        tabs.addTab(self._build_status_tab(),   "Stato")
        tabs.addTab(self._build_stats_tab(),    "Statistiche")
        tabs.addTab(self._build_history_tab(),  "Storico")
        tabs.addTab(self._build_settings_tab(), "Impostazioni")
        root.addWidget(tabs)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    # ------------------------------------------------------------------ #
    #  Printer selector helpers                                           #
    # ------------------------------------------------------------------ #

    def _on_printer_changed(self, idx: int) -> None:
        self._printer_cfg = self._cfg.printers[idx]
        self.printer_selected.emit(idx)

    def selected_printer_index(self) -> int:
        if hasattr(self, "_combo_printers"):
            return self._combo_printers.currentIndex()
        return 0

    # ------------------------------------------------------------------ #
    #  Tab Stato                                                           #
    # ------------------------------------------------------------------ #

    def _build_status_tab(self) -> QWidget:
        widget = QWidget()
        root = QVBoxLayout(widget)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 12)

        self.lbl_model = QLabel(self._printer_cfg.name)
        self.lbl_model.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_serial = QLabel("S/N: —  |  Firmware: —  |  RAM: — MB")
        self.lbl_serial.setStyleSheet("color: gray; font-size: 10px;")

        self.lbl_status = QLabel("Offline")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFixedHeight(26)
        self.lbl_status.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._set_status_style("offline")

        hdr = QHBoxLayout()
        hdr_text = QVBoxLayout()
        hdr_text.addWidget(self.lbl_model)
        hdr_text.addWidget(self.lbl_serial)
        hdr.addLayout(hdr_text)
        hdr.addStretch()
        hdr.addWidget(self.lbl_status)
        root.addLayout(hdr)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        self.gauge_toner = CircularGauge("Toner")
        self.gauge_drum  = CircularGauge("Tamburo")
        gauges = QHBoxLayout()
        gauges.addStretch()
        gauges.addWidget(self.gauge_toner)
        gauges.addSpacing(60)
        gauges.addWidget(self.gauge_drum)
        gauges.addStretch()
        root.addLayout(gauges)
        root.addStretch()

        self.lbl_updated = QLabel("Ultimo aggiornamento: —")
        self.lbl_updated.setStyleSheet("color: gray; font-size: 10px;")
        btn_scan = QPushButton("Scansiona")
        btn_scan.setObjectName("btn_scan")
        btn_scan.clicked.connect(self._start_scan)
        btn_refresh = QPushButton("Aggiorna ora")
        btn_refresh.setObjectName("btn_refresh")
        btn_refresh.clicked.connect(self.refresh_requested)
        footer = QHBoxLayout()
        footer.addWidget(self.lbl_updated)
        footer.addStretch()
        footer.addWidget(btn_scan)
        footer.addWidget(btn_refresh)
        root.addLayout(footer)

        return widget

    def _set_status_style(self, status: str) -> None:
        color = _STATUS_COLOR.get(status, "#9e9e9e")
        self.lbl_status.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px;"
            "padding:2px 12px; font-weight:bold; font-size:11px;"
        )

    # ------------------------------------------------------------------ #
    #  Tab Statistiche                                                     #
    # ------------------------------------------------------------------ #

    def _build_stats_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        pg = QGroupBox("Pagine stampate")
        pf = QFormLayout(pg)
        self.lbl_pages_total  = QLabel("—")
        self.lbl_pages_duplex = QLabel("—")
        self.lbl_pages_copy   = QLabel("—")
        self.lbl_pages_scan   = QLabel("—")
        self.lbl_coverage     = QLabel("—")
        pf.addRow("Totale:",                self.lbl_pages_total)
        pf.addRow("Fronte/retro:",          self.lbl_pages_duplex)
        pf.addRow("Copie:",                 self.lbl_pages_copy)
        pf.addRow("Scansioni:",             self.lbl_pages_scan)
        pf.addRow("Copertura media toner:", self.lbl_coverage)
        layout.addWidget(pg)

        dev = QGroupBox("Informazioni dispositivo")
        df = QFormLayout(dev)
        self.lbl_dev_serial   = QLabel("—")
        self.lbl_dev_firmware = QLabel("—")
        self.lbl_dev_memory   = QLabel("—")
        df.addRow("Numero seriale:", self.lbl_dev_serial)
        df.addRow("Firmware:",       self.lbl_dev_firmware)
        df.addRow("Memoria:",        self.lbl_dev_memory)
        layout.addWidget(dev)

        jg = QGroupBox("Inceppamenti carta")
        jf = QFormLayout(jg)
        self.lbl_jams_total  = QLabel("—")
        self.lbl_jams_tray1  = QLabel("—")
        self.lbl_jams_inside = QLabel("—")
        self.lbl_jams_rear   = QLabel("—")
        jf.addRow("Totale:",     self.lbl_jams_total)
        jf.addRow("Vassoio 1:", self.lbl_jams_tray1)
        jf.addRow("Interno:",   self.lbl_jams_inside)
        jf.addRow("Posteriore:", self.lbl_jams_rear)
        layout.addWidget(jg)

        rg = QGroupBox("Sostituzioni componenti")
        rf = QFormLayout(rg)
        self.lbl_replace_toner = QLabel("—")
        self.lbl_replace_drum  = QLabel("—")
        rf.addRow("Toner sostituiti:",   self.lbl_replace_toner)
        rf.addRow("Tamburi sostituiti:", self.lbl_replace_drum)
        layout.addWidget(rg)

        eg = QGroupBox("Storico errori (ultimi 10)")
        el = QVBoxLayout(eg)
        self.tbl_errors = QTableWidget(0, 2)
        self.tbl_errors.setHorizontalHeaderLabels(["Errore", "Pag."])
        self.tbl_errors.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tbl_errors.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_errors.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_errors.setAlternatingRowColors(True)
        self.tbl_errors.setFixedHeight(200)
        el.addWidget(self.tbl_errors)
        layout.addWidget(eg)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------ #
    #  Tab Impostazioni                                                    #
    # ------------------------------------------------------------------ #

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        ng = QGroupBox("Notifiche")
        nf = QFormLayout(ng)
        self.chk_notifications = QCheckBox("Abilita notifiche")
        self.chk_notifications.setChecked(self._printer_cfg.notifications.enabled)
        nf.addRow(self.chk_notifications)

        self.slider_toner = QSlider(Qt.Orientation.Horizontal)
        self.slider_toner.setRange(5, 50)
        self.slider_toner.setValue(self._printer_cfg.notifications.toner_threshold)
        self.lbl_toner_thresh = QLabel(f"{self.slider_toner.value()}%")
        self.slider_toner.valueChanged.connect(
            lambda v: self.lbl_toner_thresh.setText(f"{v}%"))
        t_row = QHBoxLayout()
        t_row.addWidget(self.slider_toner)
        t_row.addWidget(self.lbl_toner_thresh)
        nf.addRow("Soglia toner:", t_row)

        self.slider_drum = QSlider(Qt.Orientation.Horizontal)
        self.slider_drum.setRange(5, 30)
        self.slider_drum.setValue(self._printer_cfg.notifications.drum_threshold)
        self.lbl_drum_thresh = QLabel(f"{self.slider_drum.value()}%")
        self.slider_drum.valueChanged.connect(
            lambda v: self.lbl_drum_thresh.setText(f"{v}%"))
        d_row = QHBoxLayout()
        d_row.addWidget(self.slider_drum)
        d_row.addWidget(self.lbl_drum_thresh)
        nf.addRow("Soglia tamburo:", d_row)
        layout.addWidget(ng)

        pg = QGroupBox("Aggiornamento automatico")
        pf = QFormLayout(pg)
        self.combo_interval = QComboBox()
        self.combo_interval.addItems(["30 secondi", "1 minuto", "5 minuti"])
        self.combo_interval.setCurrentIndex(
            {30: 0, 60: 1, 300: 2}.get(self._printer_cfg.polling_interval_sec, 1))
        pf.addRow("Intervallo:", self.combo_interval)
        layout.addWidget(pg)

        sg = QGroupBox("Sistema")
        sl = QVBoxLayout(sg)
        self.chk_autostart = QCheckBox("Avvia automaticamente al login")
        self.chk_autostart.setChecked(AUTOSTART_PATH.exists())
        self.chk_autostart.toggled.connect(self._toggle_autostart)
        sl.addWidget(self.chk_autostart)
        layout.addWidget(sg)

        ag = QGroupBox("Azioni")
        al = QVBoxLayout(ag)
        btn_web = QPushButton("Apri interfaccia web")
        btn_web.clicked.connect(
            lambda: webbrowser.open(
                f"{self._printer_cfg.url}/general/status.html"))
        btn_test = QPushButton("Stampa pagina di prova")
        btn_test.clicked.connect(self._print_test_page)
        al.addWidget(btn_web)
        al.addWidget(btn_test)
        layout.addWidget(ag)

        btn_save = QPushButton("Salva impostazioni")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Azioni                                                              #
    # ------------------------------------------------------------------ #

    def _toggle_autostart(self, enabled: bool) -> None:
        AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
        if enabled:
            exec_path = f"{sys.executable} -m printer_monitor"
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Printer Monitor\n"
                f"Exec={exec_path}\n"
                "Icon=printer\n"
                "Comment=Monitoraggio stampanti\n"
                "X-KDE-autostart-enabled=true\n"
            )
            AUTOSTART_PATH.write_text(content)
        else:
            AUTOSTART_PATH.unlink(missing_ok=True)

    def _start_scan(self) -> None:
        for cmd in ("simple-scan", "xsane", "gscan2pdf"):
            try:
                subprocess.Popen([cmd])
                return
            except FileNotFoundError:
                continue
        QMessageBox.warning(
            self,
            "Scanner non trovato",
            "Nessun programma di scansione trovato.\n"
            "Installa simple-scan:\n\n"
            "  sudo apt install simple-scan",
        )

    def _print_test_page(self) -> None:
        cups = self._printer_cfg.cups_printer
        if not cups:
            return
        subprocess.Popen([
            "lp", "-d", cups,
            "-o", "media=A4",
            "-o", "print-scaling=fit",
            "/usr/share/cups/data/testprint",
        ])

    def _save_settings(self) -> None:
        n = self._printer_cfg.notifications
        n.enabled = self.chk_notifications.isChecked()
        n.toner_threshold = self.slider_toner.value()
        n.drum_threshold  = self.slider_drum.value()
        secs = {0: 30, 1: 60, 2: 300}[self.combo_interval.currentIndex()]
        self._printer_cfg.polling_interval_sec = secs
        self.refresh_interval_changed.emit(secs)
        self.config_saved.emit(self._cfg)

    # ------------------------------------------------------------------ #
    #  Update UI                                                           #
    # ------------------------------------------------------------------ #

    def update_data(self, data: PrinterData, timestamp: str) -> None:
        if data.model:
            self.lbl_model.setText(data.model)
        info_parts = []
        if data.serial:
            info_parts.append(f"S/N: {data.serial}")
        if data.firmware:
            info_parts.append(f"Firmware: {data.firmware}")
        if data.memory_mb:
            info_parts.append(f"RAM: {data.memory_mb} MB")
        self.lbl_serial.setText("  |  ".join(info_parts) if info_parts else "S/N: —")

        label = _STATUS_LABEL.get(data.status,
                                   data.status_detail or data.status.capitalize())
        self.lbl_status.setText(label)
        self._set_status_style(data.status)

        self.gauge_toner.set_value(data.toner_pct)
        self.gauge_drum.set_value(data.drum_pct)
        self.lbl_updated.setText(f"Ultimo aggiornamento: {timestamp}")

        self.lbl_pages_total.setText(str(data.page_count))
        self.lbl_coverage.setText(f"{data.avg_coverage:.2f}%")
        ps = data.page_stats
        self.lbl_pages_duplex.setText(str(ps.get("duplex", "—")))
        self.lbl_pages_copy.setText(str(ps.get("copy", "—")))
        self.lbl_pages_scan.setText(str(ps.get("scan", "—")))

        if data.serial:
            self.lbl_dev_serial.setText(data.serial)
        if data.firmware:
            self.lbl_dev_firmware.setText(data.firmware)
        if data.memory_mb:
            self.lbl_dev_memory.setText(f"{data.memory_mb} MB")

        j = data.jams
        self.lbl_jams_total.setText(str(j.get("total", 0)))
        self.lbl_jams_tray1.setText(str(j.get("tray1", 0)))
        self.lbl_jams_inside.setText(str(j.get("inside", 0)))
        self.lbl_jams_rear.setText(str(j.get("rear", 0)))

        rc = data.replace_counts
        self.lbl_replace_toner.setText(str(rc.get("toner", 0)))
        self.lbl_replace_drum.setText(str(rc.get("drum", 0)))

        self.tbl_errors.setRowCount(len(data.errors))
        for i, err in enumerate(data.errors):
            self.tbl_errors.setItem(i, 0, QTableWidgetItem(err.get("desc", "")))
            self.tbl_errors.setItem(i, 1, QTableWidgetItem(str(err.get("page", 0))))

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Ultime letture:"))
        hdr.addStretch()
        btn_clear = QPushButton("Cancella storico")
        btn_clear.setObjectName("btn_clear_history")
        btn_clear.clicked.connect(self._clear_history_requested)
        hdr.addWidget(btn_clear)
        layout.addLayout(hdr)

        self.tbl_history = QTableWidget(0, 5)
        self.tbl_history.setHorizontalHeaderLabels(
            ["Data/Ora", "Stato", "Toner %", "Tamburo %", "Pagine"])
        hdr_h = self.tbl_history.horizontalHeader()
        hdr_h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr_h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr_h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr_h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr_h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_history.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_history)

        return widget

    def update_history(self, rows: list[dict]) -> None:
        """Populate the Storico tab with rows from HistoryDB.get_recent()."""
        self.tbl_history.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.tbl_history.setItem(i, 0, QTableWidgetItem(row["timestamp"]))
            self.tbl_history.setItem(i, 1, QTableWidgetItem(row["status"]))
            self.tbl_history.setItem(i, 2, QTableWidgetItem(str(row["toner_pct"])))
            self.tbl_history.setItem(i, 3, QTableWidgetItem(str(row["drum_pct"])))
            self.tbl_history.setItem(i, 4, QTableWidgetItem(str(row["page_count"])))

    def _clear_history_requested(self) -> None:
        self.tbl_history.setRowCount(0)
        self.clear_history_requested.emit()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
