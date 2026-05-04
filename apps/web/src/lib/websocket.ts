/**
 * WebSocket Client (Drug Designer §57)
 *
 * Manages WebSocket connection for real-time run progress events.
 * §57.3 Event types: run.progress, run.stage_complete, run.error,
 * run.paused, run.complete
 *
 * Auto-reconnects on disconnect with exponential backoff.
 */

import type { RunEvent } from "./types";

type EventHandler = (event: RunEvent) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 100; // ms — starts at 100ms, doubles each attempt, capped at 30s
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _connected = false;
  private _permanentlyFailed = false;
  private lastSeenTs: string | null = null;
  private _visibilityHandler: (() => void) | null = null;

  constructor(baseUrl?: string) {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = baseUrl || `${wsProtocol}//${window.location.host}`;
    this.url = `${host}/ws/runs`;
  }

  get connected(): boolean {
    return this._connected;
  }

  /** True after all reconnect attempts have been exhausted. */
  get permanentlyFailed(): boolean {
    return this._permanentlyFailed;
  }

  connect(): void {
    if (this._permanentlyFailed) return;
    if (this.ws?.readyState === WebSocket.OPEN) return;

    // §E3: Re-connect when tab becomes visible and socket is not open
    if (!this._visibilityHandler) {
      this._visibilityHandler = () => {
        if (document.visibilityState === "visible" && !this._connected && !this._permanentlyFailed) {
          if (import.meta.env.DEV) console.log("[WS] Tab visible — attempting reconnect");
          this.reconnectAttempts = 0; // reset so visibility reconnect always tries
          this.connect();
        }
      };
      document.addEventListener("visibilitychange", this._visibilityHandler);
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this._connected = true;
        this._permanentlyFailed = false;
        const isReconnect = this.reconnectAttempts > 0;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 100;
        console.log("[WS] Connected to", this.url);
        this.emit("__connected", {} as any);

        // §57.4: Send sync message on reconnect so server can replay missed events
        if (isReconnect && this.lastSeenTs) {
          this.ws?.send(JSON.stringify({ event: "sync", last_seen_ts: this.lastSeenTs }));
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data: RunEvent = JSON.parse(event.data);
          // §57.4: Track last seen timestamp for reconnect sync
          if (data.timestamp) {
            this.lastSeenTs = data.timestamp;
          } else {
            this.lastSeenTs = new Date().toISOString();
          }
          this.emit(data.event, data);
          this.emit("*", data); // wildcard handler
        } catch (err) {
          if (import.meta.env.DEV) console.error("[WS] Failed to parse message:", err);
        }
      };

      this.ws.onclose = (event) => {
        this._connected = false;
        if (import.meta.env.DEV) console.log("[WS] Disconnected:", event.code, event.reason);
        this.emit("__disconnected", {} as any);
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        if (import.meta.env.DEV) console.error("[WS] Error:", error);
      };
    } catch (err) {
      if (import.meta.env.DEV) console.error("[WS] Connection failed:", err);
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this._visibilityHandler) {
      document.removeEventListener("visibilitychange", this._visibilityHandler);
      this._visibilityHandler = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // prevent reconnect
    this.ws?.close(1000, "Client disconnect");
    this.ws = null;
    this._connected = false;
  }

  /**
   * Subscribe to a specific event type or '*' for all events.
   * Returns an unsubscribe function.
   */
  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);

    return () => {
      this.handlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * Subscribe to events for a specific run only.
   */
  onRun(runId: string, handler: EventHandler): () => void {
    return this.on("*", (event) => {
      if (event.run_id === runId) {
        handler(event);
      }
    });
  }

  private emit(eventType: string, event: RunEvent): void {
    this.handlers.get(eventType)?.forEach((handler) => {
      try {
        handler(event);
      } catch (err) {
        console.error("[WS] Handler error:", err);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this._permanentlyFailed = true;
      console.error("[WS] Max reconnect attempts reached — connection permanently lost");
      this.emit("__connection_lost", {} as any);
      return;
    }

    // §E3: Exponential backoff starting at 100ms, capped at 30s
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    if (import.meta.env.DEV) {
      console.log(
        `[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
      );
    }

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }
}

// Singleton instance for app-wide use
let _instance: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient {
  if (!_instance) {
    _instance = new WebSocketClient();
  }
  return _instance;
}
