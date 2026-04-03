/**
 * Main application — wires map, device status, and API calls together.
 */

(function () {
    // DOM refs
    const latInput = document.getElementById("lat-input");
    const lonInput = document.getElementById("lon-input");
    const btnSet = document.getElementById("btn-set");
    const btnClear = document.getElementById("btn-clear");
    const btnSearch = document.getElementById("btn-search");
    const searchInput = document.getElementById("search-input");
    const toastEl = document.getElementById("toast");

    const statusEl = document.getElementById("device-status");
    const statusText = document.getElementById("status-text");
    const deviceInfo = document.getElementById("device-info");
    const deviceName = document.getElementById("device-name");
    const deviceModel = document.getElementById("device-model");
    const deviceIos = document.getElementById("device-ios");
    const tunnelStatus = document.getElementById("tunnel-status");
    const devmodeBanner = document.getElementById("devmode-banner");
    const btnRevealDevmode = document.getElementById("btn-reveal-devmode");
    const btnRecheckDevmode = document.getElementById("btn-recheck-devmode");

    let deviceConnected = false;
    let toastTimeout = null;

    // ---- Toast notifications (replaces alert()) ----

    function showToast(message, type) {
        type = type || "info";
        if (toastTimeout) clearTimeout(toastTimeout);
        toastEl.textContent = message;
        toastEl.className = "show " + type;
        toastTimeout = setTimeout(() => {
            toastEl.className = "";
        }, 3500);
    }

    // ---- Dismiss keyboard helper ----

    function dismissKeyboard() {
        if (document.activeElement && document.activeElement.blur) {
            document.activeElement.blur();
        }
    }

    // ---- API helpers ----

    async function apiSetLocation(lat, lon) {
        try {
            const resp = await fetch("/api/location/set", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lat, lon }),
            });
            const data = await resp.json();
            if (!data.success) {
                showToast("Failed: " + (data.error || "Unknown error"), "error");
            }
            return data;
        } catch (e) {
            showToast("Network error: " + e.message, "error");
            return { success: false };
        }
    }

    async function apiClearLocation() {
        try {
            const resp = await fetch("/api/location/clear", { method: "POST" });
            const data = await resp.json();
            if (!data.success) {
                showToast("Failed: " + (data.error || "Unknown error"), "error");
            } else {
                showToast("Location restored to real GPS", "success");
            }
            return data;
        } catch (e) {
            showToast("Network error: " + e.message, "error");
            return { success: false };
        }
    }

    // ---- UI state ----

    function updateDeviceUI(device, tunnel) {
        devmodeBanner.classList.add("hidden");

        if (!device) {
            statusEl.className = "status disconnected";
            statusText.textContent = "No device connected";
            deviceInfo.classList.add("hidden");
            deviceConnected = false;
            btnSet.disabled = true;
            btnClear.disabled = true;
            return;
        }

        deviceName.textContent = device.name;
        deviceModel.textContent = device.model;
        deviceIos.textContent = device.ios_version;
        deviceInfo.classList.remove("hidden");

        if (tunnel === "connected") {
            statusEl.className = "status connected";
            statusText.textContent = device.name + " — Ready";
            tunnelStatus.textContent = "Connected";
            deviceConnected = true;
            btnSet.disabled = false;
            btnClear.disabled = false;
        } else if (tunnel === "connecting") {
            statusEl.className = "status connecting";
            statusText.textContent = device.name + " — Connecting...";
            tunnelStatus.textContent = "Connecting...";
            deviceConnected = false;
            btnSet.disabled = true;
            btnClear.disabled = true;
        } else {
            statusEl.className = "status error";
            statusText.textContent = device.name + " — Error";
            tunnelStatus.textContent = tunnel || "Error";
            deviceConnected = false;
            btnSet.disabled = true;
            btnClear.disabled = true;
        }
    }

    function showDevmodeBanner(device) {
        deviceName.textContent = device.name;
        deviceModel.textContent = device.model;
        deviceIos.textContent = device.ios_version;
        deviceInfo.classList.remove("hidden");
        tunnelStatus.textContent = "Needs Developer Mode";
        statusEl.className = "status error";
        statusText.textContent = device.name + " — Developer Mode Off";
        devmodeBanner.classList.remove("hidden");
        deviceConnected = false;
        btnSet.disabled = true;
        btnClear.disabled = true;
    }

    function updateCoordInputs(lat, lon) {
        latInput.value = lat.toFixed(6);
        lonInput.value = lon.toFixed(6);
    }

    // ---- Map click handler ----

    function onMapClick(lat, lon) {
        updateCoordInputs(lat, lon);
        dismissKeyboard();
        if (deviceConnected) {
            apiSetLocation(lat, lon);
        }
    }

    // ---- WebSocket events ----

    let lastStatusFetch = 0;

    DeviceClient.onEvent((event, data) => {
        switch (event) {
            case "status":
                updateDeviceUI(data.device, data.tunnel);
                if (data.spoofed_location) {
                    updateCoordInputs(data.spoofed_location.lat, data.spoofed_location.lon);
                    SpoofMap.setMarker(data.spoofed_location.lat, data.spoofed_location.lon);
                }
                break;

            case "device_connected":
                updateDeviceUI(data, "connecting");
                showToast("iPhone detected — connecting...", "info");
                break;

            case "developer_mode_needed":
                showDevmodeBanner(data);
                showToast("Developer Mode required — follow the steps below", "error");
                break;

            case "device_disconnected":
                updateDeviceUI(null, "disconnected");
                SpoofMap.clearMarker();
                showToast("iPhone disconnected", "error");
                break;

            case "tunnel_status": {
                // Debounce: don't fetch more than once per 2s
                const now = Date.now();
                if (now - lastStatusFetch < 2000) break;
                lastStatusFetch = now;
                fetch("/api/device")
                    .then((r) => r.json())
                    .then((s) => {
                        updateDeviceUI(s.device, s.tunnel);
                        if (s.tunnel === "connected") {
                            showToast("Ready — tap the map to spoof!", "success");
                        }
                    });
                break;
            }

            case "location_set":
                updateCoordInputs(data.lat, data.lon);
                SpoofMap.setMarker(data.lat, data.lon);
                break;

            case "location_cleared":
                SpoofMap.clearMarker();
                latInput.value = "";
                lonInput.value = "";
                break;
        }
    });

    // ---- Button handlers ----

    btnSet.addEventListener("click", () => {
        const lat = parseFloat(latInput.value);
        const lon = parseFloat(lonInput.value);
        if (isNaN(lat) || isNaN(lon)) {
            showToast("Enter coordinates or tap the map", "error");
            return;
        }
        dismissKeyboard();
        SpoofMap.setMarker(lat, lon);
        SpoofMap.flyTo(lat, lon);
        apiSetLocation(lat, lon);
    });

    btnClear.addEventListener("click", () => {
        dismissKeyboard();
        apiClearLocation();
        SpoofMap.clearMarker();
    });

    // ---- Search ----

    async function doSearch() {
        const q = searchInput.value.trim();
        if (!q) return;
        dismissKeyboard();
        const found = await SpoofMap.searchPlace(q);
        if (found) {
            searchInput.value = "";
        } else {
            showToast("Place not found: " + q, "error");
        }
    }

    btnSearch.addEventListener("click", doSearch);
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") doSearch();
    });

    // ---- Developer Mode buttons ----

    btnRevealDevmode.addEventListener("click", async () => {
        btnRevealDevmode.disabled = true;
        btnRevealDevmode.textContent = "Revealing...";
        try {
            const resp = await fetch("/api/developer-mode/reveal", { method: "POST" });
            const data = await resp.json();
            if (data.success) {
                showToast("Toggle revealed! Now enable it in Settings", "success");
                btnRevealDevmode.textContent = "Done — Check Settings";
            } else {
                showToast("Failed: " + (data.error || "Unknown error"), "error");
                btnRevealDevmode.textContent = "Reveal Developer Mode";
                btnRevealDevmode.disabled = false;
            }
        } catch (e) {
            showToast("Network error: " + e.message, "error");
            btnRevealDevmode.textContent = "Reveal Developer Mode";
            btnRevealDevmode.disabled = false;
        }
    });

    btnRecheckDevmode.addEventListener("click", async () => {
        btnRecheckDevmode.disabled = true;
        btnRecheckDevmode.textContent = "Checking...";
        try {
            const resp = await fetch("/api/developer-mode/recheck", { method: "POST" });
            const data = await resp.json();
            if (data.success && data.developer_mode) {
                showToast("Developer Mode enabled! Connecting...", "success");
                devmodeBanner.classList.add("hidden");
            } else if (data.success && !data.developer_mode) {
                showToast("Developer Mode still off — enable it in Settings", "error");
            } else {
                showToast("Error: " + (data.error || "Unknown"), "error");
            }
        } catch (e) {
            showToast("Network error: " + e.message, "error");
        }
        btnRecheckDevmode.textContent = "Check Again";
        btnRecheckDevmode.disabled = false;
    });

    // ---- Init ----

    SpoofMap.init(onMapClick);
    DeviceClient.connect();

    // Initial status fetch
    fetch("/api/device")
        .then((r) => r.json())
        .then((s) => updateDeviceUI(s.device, s.tunnel))
        .catch(() => {});
})();
