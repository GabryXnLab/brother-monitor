# config.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

_CONFIG_PATH = Path.home() / ".config" / "printer-monitor" / "config.yaml"
_CONFIG_PATH_LEGACY = Path.home() / ".config" / "gabry" / "printer-monitor.yaml"


@dataclass
class NotifConfig:
    enabled: bool = True
    toner_threshold: int = 20
    drum_threshold: int = 15


@dataclass
class PrinterConfig:
    name: str = "Brother DCP-L2550DN"
    driver: str = "brother_http"          # "brother_http" | "snmp"
    url: str = "http://localhost:60000"    # used by brother_http driver
    cups_printer: str = "Brother_DCP-L2550DN"  # used for test-print via lp; must match the CUPS queue name (lpstat -p)
    host: str = ""                         # used by snmp driver
    community: str = "public"             # used by snmp driver
    polling_interval_sec: int = 60
    notifications: NotifConfig = field(default_factory=NotifConfig)


@dataclass
class AppConfig:
    printers: list[PrinterConfig] = field(
        default_factory=lambda: [PrinterConfig()]
    )


def load_config(path: Path = _CONFIG_PATH) -> AppConfig:
    """Load config from YAML. Returns defaults if file does not exist.

    Automatically migrates from the legacy path (~/.config/gabry/) on first run.
    """
    if not path.exists() and path == _CONFIG_PATH and _CONFIG_PATH_LEGACY.exists():
        # Silent migration: copy legacy config to new location
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_CONFIG_PATH_LEGACY.read_text())
    if not path.exists():
        return AppConfig()
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception:
        raw = None
    if not isinstance(raw, dict):
        raw = {}
    printers = []
    for p in raw.get("printers", []):
        notif_raw = p.get("notifications", {})
        notif = NotifConfig(
            enabled=notif_raw.get("enabled", True),
            toner_threshold=notif_raw.get("toner_threshold", 20),
            drum_threshold=notif_raw.get("drum_threshold", 15),
        )
        printers.append(PrinterConfig(
            name=p.get("name", "Printer"),
            driver=p.get("driver", "brother_http"),
            url=p.get("url", "http://localhost:60000"),
            cups_printer=p.get("cups_printer", ""),
            host=p.get("host", ""),
            community=p.get("community", "public"),
            polling_interval_sec=p.get("polling_interval_sec", 60),
            notifications=notif,
        ))
    return AppConfig(printers=printers if printers else [PrinterConfig()])


def save_config(cfg: AppConfig, path: Path = _CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"printers": []}
    for p in cfg.printers:
        data["printers"].append({
            "name": p.name,
            "driver": p.driver,
            "url": p.url,
            "cups_printer": p.cups_printer,
            "host": p.host,
            "community": p.community,
            "polling_interval_sec": p.polling_interval_sec,
            "notifications": {
                "enabled": p.notifications.enabled,
                "toner_threshold": p.notifications.toner_threshold,
                "drum_threshold": p.notifications.drum_threshold,
            },
        })
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
