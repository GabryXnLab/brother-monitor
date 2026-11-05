# printer_monitor/widgets.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont


class CircularGauge(QWidget):
    """Widget circolare che mostra una percentuale con arco colorato."""

    COLOR_GREEN  = QColor("#4caf50")
    COLOR_YELLOW = QColor("#ff9800")
    COLOR_RED    = QColor("#f44336")
    COLOR_BG     = QColor("#e0e0e0")

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self._value: int = 0
        self.setMinimumSize(150, 170)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, value))
        self.update()

    def _arc_color(self) -> QColor:
        if self._value > 30:
            return self.COLOR_GREEN
        if self._value > 15:
            return self.COLOR_YELLOW
        return self.COLOR_RED

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 14
        gauge_size = min(w, h - 28) - margin * 2
        x = (w - gauge_size) / 2
        y = float(margin)
        rect = QRectF(x, y, gauge_size, gauge_size)

        pen_width = max(8, gauge_size // 12)

        # Arco sfondo
        bg_pen = QPen(self.COLOR_BG, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 225 * 16, -270 * 16)

        # Arco valore
        if self._value > 0:
            fg_pen = QPen(self._arc_color(), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(fg_pen)
            span = int(-270 * 16 * self._value / 100)
            painter.drawArc(rect, 225 * 16, span)

        # Percentuale al centro
        painter.setPen(QPen(self.palette().text().color()))
        font = QFont()
        font.setPointSize(max(14, gauge_size // 8))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value}%")

        # Label sotto l'arco
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        label_rect = QRectF(0.0, y + gauge_size + 4, float(w), 22.0)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self.label)
