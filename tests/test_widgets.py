# tests/test_widgets.py
from PyQt6.QtGui import QColor
from printer_monitor.widgets import CircularGauge


def test_gauge_default_value(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    assert gauge._value == 0


def test_gauge_set_value(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    gauge.set_value(75)
    assert gauge._value == 75


def test_gauge_clamps_value(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    gauge.set_value(150)
    assert gauge._value == 100
    gauge.set_value(-5)
    assert gauge._value == 0


def test_gauge_arc_color_green(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    gauge.set_value(50)
    assert gauge._arc_color() == QColor("#4caf50")


def test_gauge_arc_color_yellow(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    gauge.set_value(20)
    assert gauge._arc_color() == QColor("#ff9800")


def test_gauge_arc_color_red(qtbot):
    gauge = CircularGauge("Toner")
    qtbot.addWidget(gauge)
    gauge.set_value(10)
    assert gauge._arc_color() == QColor("#f44336")


def test_gauge_renders_without_crash(qtbot):
    gauge = CircularGauge("Tamburo")
    qtbot.addWidget(gauge)
    gauge.set_value(88)
    gauge.show()
    gauge.update()
