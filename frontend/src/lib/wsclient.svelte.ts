/** Timing constants for the connection and keepalive state machines, in milliseconds */
const PING_INTERVAL_MS = 15000;
const PONG_TIMEOUT_MS = 8000;
const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 8000;

export default class WebSocketClient {
    #ws: WebSocket | null = null;
    #address: string;
    #subscriptions: Map<string, (data: any) => void> = new Map();
    #enabled: boolean = false;
    #pingInterval: number | null = null;
    #pingTimeout: number | null = null;
    #reconnectTimer: number | null = null;
    #reconnectAttempts: number = 0;
    #waitingForPong: boolean = false;

    state = $state({
        connected: false,
        /** Time of the last message from the server, for staleness reporting */
        last_message: 0,
    });

    constructor(address: string) {
        this.#address = address;
    }

    public subscribe(event_type: string, callback: (data: any) => void) {
        this.#subscriptions.set(event_type, callback);
        // A subscription added after the connection is up needs to be sent on its own.
        if (this.#ws?.readyState === WebSocket.OPEN) {
            this.#send({ type: 'subscribe', event_types: [event_type] });
        }
    }

    public enable() {
        if (this.#enabled) {
            return;
        }
        this.#enabled = true;

        // Reconnect promptly when the tablet comes back from sleep or regains network,
        // rather than waiting out the current backoff delay.
        window.addEventListener('online', this.#handleWake);
        document.addEventListener('visibilitychange', this.#handleWake);

        this.#connect();
    }

    public disable() {
        this.#enabled = false;
        window.removeEventListener('online', this.#handleWake);
        document.removeEventListener('visibilitychange', this.#handleWake);
        this.#cancelReconnect();
        this.#stopKeepalive();
        if (this.#ws) {
            // Drop the handlers first so that the close does not schedule a reconnect.
            this.#detach(this.#ws);
            this.#ws.close();
            this.#ws = null;
        }
        this.state.connected = false;
    }

    public sendCommand(command_name: string, data: any): boolean {
        return this.#send({
            type: 'command',
            command: command_name,
            data: data,
        });
    }

    #handleWake = () => {
        if (!this.#enabled || document.visibilityState === 'hidden') {
            return;
        }
        if (this.#ws === null) {
            this.#reconnectAttempts = 0;
            this.#cancelReconnect();
            this.#connect();
        }
    };

    #send(message: object): boolean {
        if (this.#ws?.readyState !== WebSocket.OPEN) {
            console.warn('Dropping message, websocket is not open:', message);
            return false;
        }
        this.#ws.send(JSON.stringify(message));
        return true;
    }

    #detach(ws: WebSocket) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onclose = null;
        ws.onerror = null;
    }

    #connect() {
        if (!this.#enabled || this.#ws) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const full_address = `${protocol}://${this.#address}/api/websocket`;
        console.log('Attempting websocket connection to:', full_address);

        let ws: WebSocket;
        try {
            ws = new WebSocket(full_address);
        } catch (error) {
            console.error('Failed to open websocket:', error);
            this.#scheduleReconnect();
            return;
        }
        this.#ws = ws;

        ws.onopen = () => {
            console.log('WebSocket connection established');
            this.#reconnectAttempts = 0;
            this.state.connected = true;
            this.state.last_message = Date.now();
            const event_types = Array.from(this.#subscriptions.keys());
            if (event_types.length > 0) {
                this.#send({ type: 'subscribe', event_types });
            }
            this.#startKeepalive();
        };

        ws.onmessage = (event) => {
            this.state.last_message = Date.now();

            let msg: any;
            try {
                msg = JSON.parse(event.data);
            } catch (error) {
                console.error('Ignoring malformed websocket message:', error);
                return;
            }

            switch (msg.type) {
                case 'event': {
                    const callback = this.#subscriptions.get(msg.event_type);
                    if (callback) {
                        callback(msg.data);
                    } else {
                        console.warn('Got event with no registered subscription:', msg.event_type);
                    }
                    break;
                }
                case 'subscribe':
                    for (const [event_type, data] of Object.entries(msg.initial_data ?? {})) {
                        this.#subscriptions.get(event_type)?.(data);
                    }
                    break;
                case 'unsubscribe':
                    break;
                case 'reload':
                    console.log('Server requested reload');
                    window.location.reload();
                    break;
                case 'pong':
                    this.#handlePong();
                    break;
                default:
                    console.warn('Unknown websocket message type:', msg.type);
            }
        };

        ws.onclose = () => {
            this.#detach(ws);
            if (this.#ws === ws) {
                this.#ws = null;
            }
            this.state.connected = false;
            this.#stopKeepalive();
            this.#scheduleReconnect();
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            // onclose always follows onerror, which is where the reconnect is scheduled.
            ws.close();
        };
    }

    #scheduleReconnect() {
        if (!this.#enabled || this.#reconnectTimer !== null) {
            return;
        }
        // Back off gradually so that a server restart is picked up quickly while a
        // longer outage does not spin on connection attempts.
        const delay = Math.min(
            RECONNECT_BASE_DELAY_MS * 2 ** this.#reconnectAttempts,
            RECONNECT_MAX_DELAY_MS,
        );
        this.#reconnectAttempts++;
        console.log(`Server connection lost, reconnecting in ${delay}ms`);
        this.#reconnectTimer = window.setTimeout(() => {
            this.#reconnectTimer = null;
            this.#connect();
        }, delay);
    }

    #cancelReconnect() {
        if (this.#reconnectTimer !== null) {
            clearTimeout(this.#reconnectTimer);
            this.#reconnectTimer = null;
        }
    }

    #startKeepalive() {
        this.#stopKeepalive();
        this.#pingInterval = window.setInterval(() => {
            this.#sendPing();
        }, PING_INTERVAL_MS);
    }

    #stopKeepalive() {
        if (this.#pingInterval !== null) {
            clearInterval(this.#pingInterval);
            this.#pingInterval = null;
        }
        if (this.#pingTimeout !== null) {
            clearTimeout(this.#pingTimeout);
            this.#pingTimeout = null;
        }
        this.#waitingForPong = false;
    }

    #sendPing() {
        if (this.#waitingForPong) {
            return;
        }
        if (!this.#send({ type: 'ping', timestamp: Date.now() })) {
            return;
        }
        this.#waitingForPong = true;

        this.#pingTimeout = window.setTimeout(() => {
            this.#pingTimeout = null;
            if (this.#waitingForPong) {
                console.error('No pong response received, closing connection');
                this.#ws?.close();
            }
        }, PONG_TIMEOUT_MS);
    }

    #handlePong() {
        this.#waitingForPong = false;
        if (this.#pingTimeout !== null) {
            clearTimeout(this.#pingTimeout);
            this.#pingTimeout = null;
        }
    }
}
