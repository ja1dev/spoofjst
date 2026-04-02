#!/usr/bin/env bash
#
# spoofjst Pi Zero Setup Script
#
# Configures a Raspberry Pi Zero 2W as a portable iPhone location spoofer.
# Run this ONCE after flashing Raspberry Pi OS onto your SD card.
#
# Usage:
#   sudo bash setup-pi.sh
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Must run as root
[[ $EUID -ne 0 ]] && error "Run this script with sudo: sudo bash setup-pi.sh"

SPOOFJST_DIR="$(cd "$(dirname "$0")" && pwd)"
HOTSPOT_SSID="spoofjst"
HOTSPOT_PASS="spoof1234"

echo ""
echo "============================================"
echo "  spoofjst - Pi Zero Setup"
echo "============================================"
echo ""
info "This will configure your Pi Zero as a portable iPhone GPS spoofer."
echo ""

# -------------------------------------------------------
# 1. System packages (needs internet)
# -------------------------------------------------------
info "Updating package lists..."
apt-get update -qq

info "Installing system dependencies..."
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    usbmuxd libimobiledevice-utils \
    git

# -------------------------------------------------------
# 2. Install spoofjst Python package (needs internet — do before hotspot)
# -------------------------------------------------------
info "Creating Python virtual environment..."
python3 -m venv "${SPOOFJST_DIR}/.venv"

info "Installing spoofjst and dependencies (this may take 5-15 minutes on Pi Zero)..."
"${SPOOFJST_DIR}/.venv/bin/pip" install --no-cache-dir --upgrade pip
"${SPOOFJST_DIR}/.venv/bin/pip" install --no-cache-dir -e "${SPOOFJST_DIR}"

# -------------------------------------------------------
# 3. USB OTG Host Mode
# -------------------------------------------------------
info "Configuring USB OTG host mode..."

CONFIG_FILE="/boot/firmware/config.txt"
# Fallback for older Pi OS
[[ ! -f "$CONFIG_FILE" ]] && CONFIG_FILE="/boot/config.txt"

if grep -q "dtoverlay=dwc2,dr_mode=host" "$CONFIG_FILE" 2>/dev/null; then
    info "USB host mode already configured."
else
    echo "" >> "$CONFIG_FILE"
    echo "# spoofjst: Force USB OTG to host mode for iPhone connection" >> "$CONFIG_FILE"
    echo "dtoverlay=dwc2,dr_mode=host" >> "$CONFIG_FILE"
    warn "USB host mode configured. Reboot required."
fi

# -------------------------------------------------------
# 4. WiFi Hotspot — configured but NOT activated until reboot
# -------------------------------------------------------
info "Setting up WiFi hotspot (SSID: ${HOTSPOT_SSID}, Pass: ${HOTSPOT_PASS})..."

# Detect if using NetworkManager (Bookworm/Trixie) or older dhcpcd
if command -v nmcli &>/dev/null; then
    info "Detected NetworkManager — configuring hotspot via nmcli..."

    # Delete any existing spoofjst connection
    nmcli connection delete spoofjst 2>/dev/null || true

    # Remove the preconfigured WiFi client so it doesn't compete on reboot
    nmcli connection delete preconfigured 2>/dev/null || true

    # Create hotspot connection (autoconnect on boot)
    nmcli connection add \
        type wifi \
        ifname wlan0 \
        con-name spoofjst \
        autoconnect yes \
        ssid "${HOTSPOT_SSID}" \
        wifi.mode ap \
        wifi.band bg \
        wifi.channel 7 \
        ipv4.method shared \
        ipv4.addresses 192.168.4.1/24 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "${HOTSPOT_PASS}"

    nmcli connection modify spoofjst connection.autoconnect yes
    nmcli connection modify spoofjst connection.autoconnect-priority 100

    # Do NOT bring it up now — that kills the current WiFi/SSH connection.
    # It will activate automatically on reboot.
    info "Hotspot configured. Will activate after reboot."

else
    info "Using legacy networking — configuring hotspot via hostapd..."

    apt-get install -y -qq dnsmasq hostapd

    cat > /etc/hostapd/hostapd.conf << EOF
interface=wlan0
driver=nl80211
ssid=${HOTSPOT_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${HOTSPOT_PASS}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

    if [[ -f /etc/default/hostapd ]]; then
        sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
    fi

    cat > /etc/dnsmasq.d/spoofjst.conf << EOF
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=local
address=/spoof.local/192.168.4.1
EOF

    if [[ -d /etc/network/interfaces.d ]]; then
        cat > /etc/network/interfaces.d/wlan0 << EOF
auto wlan0
iface wlan0 inet static
    address 192.168.4.1
    netmask 255.255.255.0
    nohook wpa_supplicant
EOF
    fi

    if [[ -f /etc/dhcpcd.conf ]]; then
        if ! grep -q "interface wlan0" /etc/dhcpcd.conf 2>/dev/null; then
            cat >> /etc/dhcpcd.conf << EOF

# spoofjst hotspot
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
        fi
    fi

    systemctl disable wpa_supplicant 2>/dev/null || true
    systemctl unmask hostapd 2>/dev/null || true
    systemctl enable hostapd
    systemctl enable dnsmasq
fi

# -------------------------------------------------------
# 5. Systemd service (auto-start on boot)
# -------------------------------------------------------
info "Installing systemd service..."
cat > /etc/systemd/system/spoofjst.service << EOF
[Unit]
Description=spoofjst - iPhone GPS Location Spoofer
After=network.target usbmuxd.service
Wants=usbmuxd.service

[Service]
Type=simple
ExecStart=${SPOOFJST_DIR}/.venv/bin/python -m spoofjst --host 0.0.0.0 --port 80 --no-browser
WorkingDirectory=${SPOOFJST_DIR}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable spoofjst.service

# -------------------------------------------------------
# 6. usbmuxd auto-start
# -------------------------------------------------------
systemctl enable usbmuxd

# -------------------------------------------------------
# Done
# -------------------------------------------------------
echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
info "WiFi Hotspot SSID:  ${HOTSPOT_SSID}"
info "WiFi Password:      ${HOTSPOT_PASS}"
info "Web UI URL:         http://192.168.4.1"
echo ""
warn "REBOOT NOW to apply all changes:"
echo "    sudo reboot"
echo ""
info "After reboot:"
echo "    1. Connect iPhone to Pi Zero via USB (OTG adapter + cable)"
echo "    2. Tap 'Trust This Computer' on iPhone (first time only)"
echo "    3. On iPhone, join WiFi network '${HOTSPOT_SSID}' (password: ${HOTSPOT_PASS})"
echo "    4. Open Safari and go to http://192.168.4.1"
echo "    5. Click the map to spoof your location!"
echo ""
