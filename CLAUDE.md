# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run all tests (headless, no display needed)
uv run pytest

# Run a single test file
uv run pytest tests/test_brother_http_driver.py

# Run a single test by name
uv run pytest tests/test_brother_http_driver.py::test_parse_info_toner_drum

# Run the application
uv run python brother_monitor.py

# Install system-wide
bash install.sh
```

## Architecture

The app is a **PyQt6 system tray monitor** for Brother printers. It polls a printer via HTTP (Brother web interface) or SNMP and shows status in a tray icon and optional window.

### ⚠️ Connettività: USB *e* rete (non solo rete!)

> **NON assumere che serva una stampante di rete.** Il caso d'uso principale è una stampante **collegata via USB**.
>
> Il driver di default `brother_http` interroga `http://localhost:60000`. Quella porta **non** è la stampante in rete: è il bridge **`ipp-usb`** (systemd service `ipp-usb.service`, demone `/sbin/ipp-usb`) che espone via HTTP su `localhost` l'interfaccia web di una stampante collegata in **USB** (IPP-over-USB, interfaccia `070104`). `ipp-usb` viene avviato automaticamente da una regola udev (`/usr/lib/udev/rules.d/71-ipp-usb.rules`) quando colleghi la stampante, e assegna la prima porta libera a partire da `60000`.
>
> Quindi: **USB → `ipp-usb` (localhost:60000) → driver `brother_http` → dati**. La modalità SNMP/rete (`driver: snmp`, campo `host`) è un'alternativa, non l'unico modo.
>
> Diagnosi rapida se "non si attiva":
> 1. La stampante è vista da USB? `lsusb | grep -i brother`
> 2. `ipp-usb` è attivo e la porta risponde? `systemctl status ipp-usb` + `curl -s -o /dev/null -w '%{http_code}' http://localhost:60000/general/status.html` (atteso `200`)
> 3. **L'app è in esecuzione?** `pgrep -af brother_monitor`. È una tray-app che parte al login/su evento udev, **non** è event-driven da sola: se il processo è giù, collegare la stampante non lo risveglia da solo (vedi regola udev sotto).

### Deploy / avvio automatico

`install.sh` installa l'app in `/usr/local/lib/printer-monitor`, registra un **XDG autostart** (`/etc/xdg/autostart/printer-monitor.desktop`, parte al login), un **systemd user service** (`printer-monitor.service`, con `Restart=on-failure`) e una **regola udev** (`/etc/udev/rules.d/72-printer-monitor.rules`) che avvia il servizio utente via `SYSTEMD_USER_WANTS` appena viene collegata una stampante Brother USB. Il file sorgente della regola nel repo è `printer-monitor.rules`.

**Data flow:**
1. Each `PrinterDriver.fetch()` returns a `PrinterData` dataclass.
2. `brother_monitor.py` owns one `QTimer` per printer and wires: driver → `MainWindow.update_data()` + `BrotherTray.update_all_statuses()` + `_check_notifications()`

**Key modules:**
- `drivers/base.py` — `PrinterDriver` ABC and `PrinterData` dataclass. No Qt dependency.
- `drivers/brother_http.py` — scrapes the Brother printer's built-in web UI via HTTP. Default URL `http://localhost:60000` targets the `ipp-usb` bridge for a **USB-connected** printer (see Connettività above), not a network host.
- `drivers/snmp.py` — polls printers via SNMP OIDs.
- `config.py` — YAML config at `~/.config/printer-monitor/config.yaml`. `load_config` / `save_config`.
- `history.py` — `HistoryDB`: SQLite storage for per-printer readings.
- `tray.py` — `BrotherTray(QSystemTrayIcon)`: SVG tray icon, tray menu, debounced desktop notifications (1 per key per 60 min).
- `main_window.py` — `MainWindow(QMainWindow)`: 4-tab window (Stato/Statistiche/Storico/Impostazioni). Emits `refresh_requested`, `refresh_interval_changed`, `config_saved`, `printer_selected`, `clear_history_requested`.
- `widgets.py` — `CircularGauge(QWidget)`: custom-painted arc gauge for toner/drum percentages.
- `brother_monitor.py` — entry point; creates `QApplication` and connects signals.

**Tests** use `pytest-qt` with `QT_QPA_PLATFORM=offscreen` (set in `conftest.py`). Drivers are tested by mocking HTTP responses. `tmp_path` fixture used for config and DB tests.

## ⚠️ Repository Pubblica — Sicurezza

Questo progetto ha una **repository GitHub pubblica**. Rispettare sempre queste regole:

- **Non includere mai** chiavi API, token, password, credenziali o segreti nel codice o nei commit
- Usare **variabili d'ambiente** per tutti i valori sensibili; il file `.env` non va mai committato
- Verificare che `.gitignore` escluda `.env`, `*.key`, `*.pem` e qualsiasi file con segreti
- **Non loggare** dati sensibili (token, credenziali, risposte API con dati privati)
- Non includere URL interni, IP privati o dettagli di infrastruttura interna nel codice o nei commenti
- I messaggi di commit devono essere appropriati per una audience pubblica
- Revisionare ogni diff prima del push per escludere esposizioni accidentali di dati sensibili
