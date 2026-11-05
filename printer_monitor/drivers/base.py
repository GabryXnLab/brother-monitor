from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PrinterData:
    status: str = "offline"          # idle / printing / sleep / offline / error
    status_detail: str = ""
    toner_pct: int = 0
    drum_pct: int = 0
    model: str = ""
    serial: str = ""
    firmware: str = ""
    memory_mb: int = 0
    page_count: int = 0
    avg_coverage: float = 0.0
    errors: list[dict[str, str | int]] = field(default_factory=list)
    jams: dict[str, int] = field(default_factory=dict)
    replace_counts: dict[str, int] = field(default_factory=dict)
    page_stats: dict[str, int] = field(default_factory=dict)


class PrinterDriver(ABC):
    @abstractmethod
    def fetch(self) -> PrinterData:
        """Poll the printer and return its current state."""
