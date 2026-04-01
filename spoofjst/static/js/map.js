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
            tap: true, // explicit mobile tap support
        });

        // Tile layer (OpenStreetMap)
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://openstreetmap.org/copyright">OSM</a>',
            maxZoom: 19,
        }).addTo(map);

        // Zoom controls — bottom right on mobile, top right on desktop
        const isMobile = window.innerWidth <= 480;
        L.control.zoom({ position: isMobile ? "bottomright" : "topright" }).addTo(map);

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
            `<b>Spoofed</b><br>${lat.toFixed(6)}, ${lng.toFixed(6)}`
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
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
        try {
            const resp = await fetch(url, {
                headers: { "User-Agent": "spoofjst/0.1.0" },
            });
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
