/**
 * WebSocket client for real-time device status updates.
 */

const DeviceClient = (() => {
    let ws = null;
    let reconnectTimer = null;
    const listeners = [];

    function connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${location.host}/ws`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            console.log("[ws] connected");
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };

        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                listeners.forEach((fn) => fn(msg.event, msg.data));
            } catch (e) {
                console.error("[ws] parse error:", e);
            }
        };

        ws.onclose = () => {
            console.log("[ws] disconnected, reconnecting in 2s...");
            reconnectTimer = setTimeout(connect, 2000);
        };

        ws.onerror = (err) => {
            console.error("[ws] error:", err);
            ws.close();
        };
    }

    function onEvent(fn) {
        listeners.push(fn);
    }

    function send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }

    return { connect, onEvent, send };
})();
