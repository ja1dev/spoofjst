# spoofjst Setup Guide

iPhone GPS location spoofer over USB. Works on Mac and Raspberry Pi Zero 2W.

## What You Need

**For Mac (testing):**
- MacBook with USB port
- iPhone with Lightning or USB-C cable
- Python 3.11+

**For Pi Zero 2W (portable):**
- Raspberry Pi Zero 2W (~$15)
- USB-C OTG adapter (~$8)
- MicroSD card 16GB+ (~$8)
- USB-A to Lightning/USB-C cable
- Any power bank you already own (5,000mAh+ gives 15+ hours)

## Step 1: Test on Mac

Do this first — takes 2 minutes and confirms spoofing works before touching the Pi.

```bash
# Clone the repo
git clone https://github.com/ja1dev/spoofjst.git
cd spoofjst

# Install
pip3 install -e .
```

**Prepare your iPhone:**

1. Plug iPhone into Mac via USB
2. Unlock it and tap **Trust This Computer** if prompted
3. Enable Developer Mode (one-time):
   ```bash
   sudo pymobiledevice3 amfi enable-developer-mode
   ```
   - iPhone will reboot
   - After reboot, tap **Turn On** when prompted to confirm Developer Mode
   - Note: You can also enable it via Settings → Privacy & Security → Developer Mode, but that toggle only appears after connecting to Xcode

**Run it:**

```bash
sudo python3 -m spoofjst
```

Browser opens automatically. Click the map. Your iPhone location should jump to that spot. If it works, you're good — move on to Pi setup.

## Step 2: Flash the Pi SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your Mac
2. Insert your microSD card into your Mac
3. In Imager, choose:
   - **OS:** Raspberry Pi OS Lite (32-bit)
   - **Storage:** your microSD card
4. Click the **gear icon** (⚙) before writing and set:
   - **Enable SSH:** Yes
   - **Username:** `pi`
   - **Password:** pick something (e.g. `spoof1234`)
   - **Configure WiFi:** your home WiFi name and password (needed for initial setup only — the setup script switches to hotspot mode later)
5. Click **Write** and wait for it to finish
6. Eject the SD card

## Step 3: Boot and SSH into the Pi

1. Put the SD card into the Pi Zero 2W
2. Plug your power bank into the **left micro-USB port** (labeled **PWR**)
3. Wait ~60 seconds for it to boot
4. Find its IP — try from your Mac terminal:

```bash
ping raspberrypi.local
```

If that doesn't work, check your router's admin page for a device named `raspberrypi`.

5. SSH in:

```bash
ssh pi@raspberrypi.local
```

Enter the password you set in Raspberry Pi Imager.

## Step 4: Install spoofjst on the Pi

Once you're SSH'd in:

```bash
sudo apt install git -y
git clone https://github.com/ja1dev/spoofjst.git
cd spoofjst
sudo bash setup-pi.sh
sudo reboot
```

The setup script installs everything automatically:
- USB OTG host mode
- WiFi hotspot (SSID: `spoofjst`, password: `spoof1234`)
- usbmuxd for iPhone communication
- Python dependencies
- Auto-start on boot via systemd

The Pi will reboot. After this you **no longer need your home WiFi** — the Pi runs its own hotspot.

## Step 5: Use It

1. Plug power bank into Pi's **left port** (PWR)
2. Plug iPhone into Pi's **right port** (DATA) using the USB-C OTG adapter + cable
3. Unlock iPhone, tap **Trust This Computer** (first time only)
4. On iPhone, go to **Settings → WiFi → join `spoofjst`** (password: `spoof1234`)
5. Open Safari → `http://192.168.4.1`
6. Tap the map to spoof your location

## Daily Use (After First Setup)

1. Plug in power bank → plug in iPhone
2. Join `spoofjst` WiFi
3. Open `http://192.168.4.1` in Safari
4. Tap to spoof, hit Clear to restore real GPS

Everything starts automatically on boot. No SSH needed.

## Port Layout (Pi Zero 2W)

```
[HDMI]  [LEFT/PWR]  [RIGHT/DATA]

         ↑              ↑
     Power bank     iPhone + OTG adapter
```

## Troubleshooting

**"Trust This Computer" not appearing:**
- Make sure iPhone is unlocked when you plug it in
- Try unplugging and replugging
- On the Pi, run: `sudo idevicepair pair`

**Can't find spoofjst WiFi:**
- Wait 30 seconds after Pi boots
- Make sure you ran `sudo bash setup-pi.sh` and rebooted

**Location not changing:**
- Verify Developer Mode is enabled on iPhone
- Check the web UI shows "Connected" status
- Try clearing location first, then setting a new one

**Web UI not loading:**
- Confirm you're connected to the `spoofjst` WiFi
- Try `http://192.168.4.1` (not https)
- SSH in and check: `sudo systemctl status spoofjst`

**iPhone stops responding after being locked for a while:**
- iOS USB Restricted Mode blocks USB data after 1 hour locked
- Fix: Settings → Face ID & Passcode → USB Accessories → ON
