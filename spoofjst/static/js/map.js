/**
 * Leaflet map initialization and click-to-spoof interaction.
 */

const SpoofMap = (() => {
    let map = null;
    let marker = null;
    let onLocationClick = null;

    function init(clickCallback) {
        onLocationClick = clickCallback;

        map = L.map("map", {
            center: [37.7749, -122.4194], // San Francisco default
            zoom: 13,
            zoomControl: false,
        });

        // Tile layer (OpenStreetMap)
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19,
        }).addTo(map);

        // Zoom controls — top right
        L.control.zoom({ position: "topright" }).addTo(map);

        // Click handler
        map.on("click", (e) => {
            const { lat, lng } = e.latlng;
            setMarker(lat, lng);
            if (onLocationClick) {
                onLocationClick(lat, lng);
            }
        });
    }

    function setMarker(lat, lng) {
        if (marker) {
            marker.setLatLng([lat, lng]);
        } else {
            marker = L.marker([lat, lng], {
                draggable: true,
            }).addTo(map);

            marker.on("dragend", () => {
                const pos = marker.getLatLng();
                if (onLocationClick) {
                    onLocationClick(pos.lat, pos.lng);
                }
            });
        }

        marker.bindPopup(
            `<b>Spoofed Location</b><br>${lat.toFixed(6)}, ${lng.toFixed(6)}`
        ).openPopup();
    }

    function clearMarker() {
        if (marker) {
            map.removeLayer(marker);
            marker = null;
        }
    }

    function flyTo(lat, lng, zoom) {
        map.flyTo([lat, lng], zoom || 15);
    }

    async function searchPlace(query) {
        // Nominatim geocoding (OpenStreetMap, no API key)
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
        try {
            const resp = await fetch(url);
            const results = await resp.json();
            if (results.length > 0) {
                const { lat, lon } = results[0];
                const la = parseFloat(lat);
                const lo = parseFloat(lon);
                flyTo(la, lo, 15);
                setMarker(la, lo);
                if (onLocationClick) {
                    onLocationClick(la, lo);
                }
                return true;
            }
        } catch (e) {
            console.error("Search failed:", e);
        }
        return false;
    }

    return { init, setMarker, clearMarker, flyTo, searchPlace };
})();
