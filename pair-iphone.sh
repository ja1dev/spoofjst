#!/usr/bin/env bash
#
# spoofjst iPhone Pairing Helper
#
# Run this ONCE after first connecting your iPhone to the Pi Zero.
# It handles the trust pairing and verifies the connection works.
#
# Usage:
#   sudo bash pair-iphone.sh
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; }

[[ $EUID -ne 0 ]] && { error "Run with sudo: sudo bash pair-iphone.sh"; exit 1; }

echo ""
echo "============================================"
echo "  spoofjst - iPhone Pairing"
echo "============================================"
echo ""

# Check usbmuxd is running
if ! systemctl is-active --quiet usbmuxd; then
    info "Starting usbmuxd..."
    systemctl start usbmuxd
    sleep 2
fi

# Check for connected device
info "Looking for connected iPhone..."
if ! idevice_id -l 2>/dev/null | grep -q .; then
    error "No iPhone detected!"
    echo ""
    echo "Make sure:"
    echo "  1. iPhone is plugged into the Pi's USB port via OTG adapter"
    echo "  2. The OTG adapter is in the DATA port (not PWR)"
    echo "  3. You've rebooted after running setup-pi.sh"
    echo ""
    exit 1
fi

UDID=$(idevice_id -l | head -1)
info "Found device: ${UDID}"

# Attempt pairing
echo ""
warn ">>> UNLOCK YOUR IPHONE and tap 'Trust' when prompted <<<"
echo ""
read -p "Press Enter when your iPhone is unlocked..."

info "Initiating pairing..."
if idevicepair pair 2>&1; then
    echo ""
    info "Pairing successful!"
else
    warn "Pairing may have failed. Make sure you tapped 'Trust' on the iPhone."
    warn "Try unplugging and replugging the iPhone, then run this script again."
    exit 1
fi

# Verify — read device info
echo ""
info "Verifying connection..."
DEVICE_NAME=$(ideviceinfo -k DeviceName 2>/dev/null || echo "Unknown")
IOS_VERSION=$(ideviceinfo -k ProductVersion 2>/dev/null || echo "Unknown")
MODEL=$(ideviceinfo -k ProductType 2>/dev/null || echo "Unknown")

echo ""
echo "============================================"
echo "  Device Paired Successfully!"
echo "============================================"
echo ""
info "Name:    ${DEVICE_NAME}"
info "Model:   ${MODEL}"
info "iOS:     ${IOS_VERSION}"
info "UDID:    ${UDID}"
echo ""

# Check Developer Mode
MAJOR_VERSION=$(echo "$IOS_VERSION" | cut -d. -f1)
if [[ "$MAJOR_VERSION" -ge 16 ]]; then
    info "Checking Developer Mode..."
    # Try to check developer mode status
    DEV_MODE=$(idevicedevmodectl status 2>/dev/null || echo "unknown")
    if echo "$DEV_MODE" | grep -qi "enabled"; then
        info "Developer Mode: ENABLED"
    else
        warn "Developer Mode may not be enabled."
        echo ""
        echo "To enable Developer Mode on your iPhone:"
        echo "  1. Go to Settings > Privacy & Security"
        echo "  2. Scroll down and tap 'Developer Mode'"
        echo "  3. Toggle it ON and restart your iPhone"
        echo "  4. After restart, confirm when prompted"
        echo ""
    fi
fi

echo ""
info "You're all set! spoofjst will auto-detect your iPhone on next boot."
info "Join WiFi 'spoofjst' (password: spoof1234) and open http://192.168.4.1"
echo ""
