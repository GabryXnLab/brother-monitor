# printer_monitor/history.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime

from printer_monitor.drivers.base import PrinterData

_DEFAULT_DB = Path.home() / ".local" / "share" / "printer-monitor" / "history.db"


class HistoryDB:
    def __init__(self, path: Path = _DEFAULT_DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_name TEXT    NOT NULL,
                timestamp    TEXT    NOT NULL,
                status       TEXT    NOT NULL,
                toner_pct    INTEGER NOT NULL,
                drum_pct     INTEGER NOT NULL,
                page_count   INTEGER NOT NULL
            )
        """)
        self._conn.commit()

    def record(self, printer_name: str, data: PrinterData) -> None:
        self._conn.execute(
            "INSERT INTO readings (printer_name, timestamp, status, toner_pct, drum_pct, page_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (printer_name,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             data.status,
             data.toner_pct,
             data.drum_pct,
             data.page_count),
        )
        self._conn.commit()

    def get_recent(self, printer_name: str, limit: int = 200) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM readings WHERE printer_name = ? "
            "ORDER BY id DESC LIMIT ?",
            (printer_name, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def clear(self, printer_name: str) -> None:
        self._conn.execute(
            "DELETE FROM readings WHERE printer_name = ?", (printer_name,)
        )
        self._conn.commit()
