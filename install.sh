#!/bin/bash
set -e

INSTALL_DIR="/usr/local/lib/printer-monitor"
BIN_PATH="/usr/local/bin/printer-monitor"

echo "==> Installazione Printer Monitor..."

UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ]; then
    echo "ERRORE: 'uv' non è installato. È richiesto per creare il venv"
    echo "con le dipendenze dell'app (PyQt6, requests, beautifulsoup4, pyyaml, pysnmp)."
    echo "Installalo con:"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "poi rilancia questo script."
    exit 1
fi

sudo mkdir -p "$INSTALL_DIR"
sudo cp -- brother_monitor.py config.py history.py \
           main_window.py tray.py widgets.py pyproject.toml uv.lock "$INSTALL_DIR/"
sudo cp -- *.svg "$INSTALL_DIR/" 2>/dev/null || true
sudo cp -r drivers "$INSTALL_DIR/"

echo "==> Creazione venv con uv..."
sudo "$UV_BIN" sync --frozen --no-dev --project "$INSTALL_DIR"

sudo tee "$BIN_PATH" > /dev/null << 'EOF'
#!/bin/bash
export PYTHONPATH="/usr/local/lib/printer-monitor:$PYTHONPATH"
exec /usr/local/lib/printer-monitor/.venv/bin/python3 /usr/local/lib/printer-monitor/brother_monitor.py "$@"
EOF
sudo chmod +x "$BIN_PATH"

# Autostart per tutti gli utenti (XDG system-wide)
AUTOSTART_DIR="/etc/xdg/autostart"
sudo mkdir -p "$AUTOSTART_DIR"
sudo tee "$AUTOSTART_DIR/printer-monitor.desktop" > /dev/null << EOF
[Desktop Entry]
Type=Application
Name=Printer Monitor
Exec=$BIN_PATH
Icon=printer
Comment=Monitoraggio stampanti di rete
X-GNOME-Autostart-enabled=true
X-KDE-autostart-enabled=true
EOF

# Systemd user service (disponibile per tutti gli utenti)
SERVICE_DIR="/usr/lib/systemd/user"
sudo mkdir -p "$SERVICE_DIR"
sudo tee "$SERVICE_DIR/printer-monitor.service" > /dev/null << 'EOF'
[Unit]
Description=Printer Monitor tray application
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/local/bin/printer-monitor
Restart=on-failure
RestartSec=5
Environment=PYTHONPATH=/usr/local/lib/printer-monitor

[Install]
WantedBy=graphical-session.target
EOF

sudo systemctl daemon-reload

# Regola udev: avvia il servizio utente appena si collega la stampante Brother USB
UDEV_RULE="/etc/udev/rules.d/72-printer-monitor.rules"
sudo cp -- printer-monitor.rules "$UDEV_RULE"
sudo udevadm control --reload-rules

# Verifica se la stampante USB (vista via ipp-usb) è già registrata come coda CUPS.
# Non la registra automaticamente: il nome coda è una scelta dell'utente e lpadmin
# richiede privilegi di sistema, meglio lasciarlo come comando esplicito.
if systemctl is-active --quiet ipp-usb 2>/dev/null && command -v lpstat >/dev/null 2>&1; then
    if ! lpstat -v 2>/dev/null | grep -q "localhost:600"; then
        BRIDGE_URI=$(lpinfo -v 2>/dev/null | awk '/network ipp:\/\/.*_ipp\._tcp\.local/ {print; exit}' | awk '{print $2}')
        echo ""
        echo "    NOTA: la stampante è collegata via USB (bridge ipp-usb) ma non risulta"
        echo "    ancora registrata in CUPS: per stamparci da browser/altre app serve"
        echo "    prima una coda CUPS. Registrala con IPP Everywhere (nessun driver"
        echo "    Brother necessario):"
        echo "      sudo lpadmin -p Brother -E -v \"ipp://localhost:60000/ipp/print\" -m everywhere"
        [ -n "$BRIDGE_URI" ] && echo "    (rilevato via mDNS: $BRIDGE_URI)"
    fi
fi

echo "==> Installazione completata."
echo "    Avvia con:                printer-monitor"
echo "    Si avvierà automaticamente al login (XDG autostart per tutti gli utenti)"
echo "    e appena colleghi una stampante Brother via USB (regola udev)."
echo ""
echo "    Per gestirlo via systemd (per utente):"
echo "      systemctl --user enable --now printer-monitor"
echo "      systemctl --user status printer-monitor"
echo ""
echo "    NOTA per utenti GNOME: l'icona nella tray richiede l'estensione"
echo "    'AppIndicator and KStatusNotifierItem Support' (GNOME non espone"
echo "    StatusNotifierItem in modo nativo):"
echo "      sudo dnf install -y gnome-shell-extension-appindicator"
echo "      gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com"
echo "    poi fai logout/login."
