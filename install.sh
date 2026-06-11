#!/bin/bash
set -e

INSTALL_DIR="/usr/local/lib/printer-monitor"
BIN_PATH="/usr/local/bin/printer-monitor"

echo "==> Installazione Printer Monitor..."

sudo mkdir -p "$INSTALL_DIR"
sudo cp -- brother_monitor.py config.py history.py \
           main_window.py tray.py widgets.py "$INSTALL_DIR/"
sudo cp -- *.svg "$INSTALL_DIR/" 2>/dev/null || true
sudo cp -r drivers "$INSTALL_DIR/"

sudo tee "$BIN_PATH" > /dev/null << 'EOF'
#!/bin/bash
export PYTHONPATH="/usr/local/lib/printer-monitor:$PYTHONPATH"
exec python3 /usr/local/lib/printer-monitor/brother_monitor.py "$@"
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

echo "==> Installazione completata."
echo "    Avvia con:                printer-monitor"
echo "    Si avvierà automaticamente al login (XDG autostart per tutti gli utenti)"
echo "    e appena colleghi una stampante Brother via USB (regola udev)."
echo ""
echo "    Per gestirlo via systemd (per utente):"
echo "      systemctl --user enable --now printer-monitor"
echo "      systemctl --user status printer-monitor"
