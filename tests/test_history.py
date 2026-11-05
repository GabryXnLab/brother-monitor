# tests/test_history.py
import pytest
from printer_monitor.history import HistoryDB
from printer_monitor.drivers.base import PrinterData


@pytest.fixture
def db(tmp_path):
    return HistoryDB(tmp_path / "test.db")


def test_record_and_query(db):
    data = PrinterData(status="idle", toner_pct=40, drum_pct=88, page_count=100)
    db.record("Printer A", data)
    rows = db.get_recent("Printer A", limit=10)
    assert len(rows) == 1
    assert rows[0]["toner_pct"] == 40
    assert rows[0]["drum_pct"] == 88
    assert rows[0]["status"] == "idle"
    assert rows[0]["page_count"] == 100
    assert rows[0]["printer_name"] == "Printer A"


def test_limit_respected(db):
    data = PrinterData(status="idle", toner_pct=50, drum_pct=50)
    for _ in range(20):
        db.record("P", data)
    rows = db.get_recent("P", limit=5)
    assert len(rows) == 5


def test_returns_most_recent_first(db):
    db.record("P", PrinterData(status="idle", toner_pct=90, drum_pct=90))
    db.record("P", PrinterData(status="idle", toner_pct=80, drum_pct=80))
    rows = db.get_recent("P", limit=2)
    assert rows[0]["toner_pct"] == 80  # most recent first


def test_isolates_by_printer_name(db):
    db.record("A", PrinterData(status="idle", toner_pct=10))
    db.record("B", PrinterData(status="idle", toner_pct=99))
    assert db.get_recent("A")[0]["toner_pct"] == 10
    assert db.get_recent("B")[0]["toner_pct"] == 99


def test_clear(db):
    db.record("P", PrinterData(status="idle"))
    db.clear("P")
    assert db.get_recent("P") == []
