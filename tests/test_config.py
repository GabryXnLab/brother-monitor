# tests/test_config.py
from config import load_config, save_config


def test_default_config_has_one_printer(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    assert len(cfg.printers) == 1


def test_default_printer_is_brother_http(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    p = cfg.printers[0]
    assert p.driver == "brother_http"
    assert p.url == "http://localhost:60000"
    assert p.name == "Brother DCP-L2550DN"
    assert p.cups_printer == "Brother_DCP-L2550DN"


def test_default_notif_thresholds(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    n = cfg.printers[0].notifications
    assert n.toner_threshold == 20
    assert n.drum_threshold == 15
    assert n.enabled is True


def test_default_polling_interval(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    assert cfg.printers[0].polling_interval_sec == 60


def test_save_and_reload(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = load_config(path)
    cfg.printers[0].polling_interval_sec = 30
    save_config(cfg, path)
    reloaded = load_config(path)
    assert reloaded.printers[0].polling_interval_sec == 30


def test_multiple_printers(tmp_path):
    path = tmp_path / "config.yaml"
    import yaml
    data = {
        "printers": [
            {
                "name": "Printer A",
                "driver": "brother_http",
                "url": "http://localhost:60000",
                "cups_printer": "PrinterA",
                "polling_interval_sec": 60,
                "notifications": {
                    "enabled": True,
                    "toner_threshold": 20,
                    "drum_threshold": 15,
                },
            },
            {
                "name": "Printer B",
                "driver": "snmp",
                "host": "192.168.1.10",
                "community": "public",
                "polling_interval_sec": 120,
                "notifications": {
                    "enabled": False,
                    "toner_threshold": 10,
                    "drum_threshold": 10,
                },
            },
        ]
    }
    path.write_text(yaml.dump(data))
    cfg = load_config(path)
    assert len(cfg.printers) == 2
    assert cfg.printers[1].driver == "snmp"
    assert cfg.printers[1].host == "192.168.1.10"
    assert cfg.printers[1].notifications.enabled is False
