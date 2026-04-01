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

    const statusEl = document.getElementById("device-status");
    const statusText = document.getElementById("status-text");
    const deviceInfo = document.getElementById("device-info");
    const deviceName = document.getElementById("device-name");
    const deviceModel = document.getElementById("device-model");
    const deviceIos = document.getElementById("device-ios");
    const tunnelStatus = document.getElementById("tunnel-status");

    let deviceConnected = false;

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
                alert("Failed to set location: " + (data.error || "Unknown error"));
            }
            return data;
        } catch (e) {
            alert("Network error: " + e.message);
            return { success: false };
        }
    }

    async function apiClearLocation() {
        try {
            const resp = await fetch("/api/location/clear", { method: "POST" });
            const data = await resp.json();
            if (!data.success) {
                alert("Failed to clear: " + (data.error || "Unknown error"));
            }
            return data;
        } catch (e) {
            alert("Network error: " + e.message);
            return { success: false };
        }
    }

    // ---- UI state ----

    function updateDeviceUI(device, tunnel) {
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
            statusEl.className = "status disconnected";
            statusText.textContent = device.name + " — Error";
            tunnelStatus.textContent = tunnel || "Error";
            deviceConnected = false;
            btnSet.disabled = true;
            btnClear.disabled = true;
        }
    }

    function updateCoordInputs(lat, lon) {
        latInput.value = lat.toFixed(6);
        lonInput.value = lon.toFixed(6);
    }

    // ---- Map click handler ----

    function onMapClick(lat, lon) {
        updateCoordInputs(lat, lon);
        // Auto-set if device is connected
        if (deviceConnected) {
            apiSetLocation(lat, lon);
        }
    }

    // ---- WebSocket events ----

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
                break;

            case "device_disconnected":
                updateDeviceUI(null, "disconnected");
                SpoofMap.clearMarker();
                break;

            case "tunnel_status":
                // Refresh full status
                fetch("/api/device")
                    .then((r) => r.json())
                    .then((s) => updateDeviceUI(s.device, s.tunnel));
                break;

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
            alert("Enter valid coordinates or click the map.");
            return;
        }
        SpoofMap.setMarker(lat, lon);
        SpoofMap.flyTo(lat, lon);
        apiSetLocation(lat, lon);
    });

    btnClear.addEventListener("click", () => {
        apiClearLocation();
        SpoofMap.clearMarker();
    });

    // ---- Search ----

    async function doSearch() {
        const q = searchInput.value.trim();
        if (!q) return;
        const found = await SpoofMap.searchPlace(q);
        if (!found) {
            alert("Place not found: " + q);
        }
    }

    btnSearch.addEventListener("click", doSearch);
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") doSearch();
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
