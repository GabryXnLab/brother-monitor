import pytest
from printer_monitor.drivers.base import PrinterData, PrinterDriver


def test_printer_data_defaults():
    d = PrinterData()
    assert d.status == "offline"
    assert d.toner_pct == 0
    assert d.drum_pct == 0
    assert d.errors == []
    assert d.jams == {}
    assert d.replace_counts == {}
    assert d.page_stats == {}


def test_printer_driver_is_abstract():
    with pytest.raises(TypeError):
        PrinterDriver()  # cannot instantiate ABC


def test_concrete_driver_must_implement_fetch():
    class BadDriver(PrinterDriver):
        pass  # no fetch() → still abstract
    with pytest.raises(TypeError):
        BadDriver()


def test_concrete_driver_can_be_instantiated():
    class GoodDriver(PrinterDriver):
        def fetch(self) -> PrinterData:
            return PrinterData(status="idle")
    d = GoodDriver()
    assert d.fetch().status == "idle"
