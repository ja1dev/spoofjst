/**
 * WebSocket client for real-time device status updates.
 * Includes exponential backoff reconnection for mobile battery efficiency.
 */

const DeviceClient = (() => {
    let ws = null;
    let reconnectTimer = null;
    let reconnectDelay = 2000;
    const MAX_RECONNECT_DELAY = 16000;
    const listeners = [];
    let pingInterval = null;

    function connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${location.host}/ws`;

        ws = new WebSocket(url);

        // Connection timeout — if no open event in 10s, retry
        const connectTimeout = setTimeout(() => {
            if (ws.readyState !== WebSocket.OPEN) {
                ws.close();
            }
        }, 10000);

        ws.onopen = () => {
            clearTimeout(connectTimeout);
            reconnectDelay = 2000; // reset backoff on successful connect

            // Keep-alive ping every 30s (iOS kills idle connections)
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send("ping");
                }
            }, 30000);
        };

        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                listeners.forEach((fn) => fn(msg.event, msg.data));
            } catch (e) {
                // ignore non-JSON (pong responses etc.)
            }
        };

        ws.onclose = () => {
            clearTimeout(connectTimeout);
            if (pingInterval) {
                clearInterval(pingInterval);
                pingInterval = null;
            }
            // Exponential backoff: 2s, 4s, 8s, 16s max
            reconnectTimer = setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
        };

        ws.onerror = () => {
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
