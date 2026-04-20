/**
 * eVoca API service — REST and WebSocket client for the mobile app.
 *
 * Connects to the eVoca FastAPI server with authentication,
 * auto-reconnection, and streaming token support.
 */

export interface ServerConfig {
  host: string;       // e.g. "192.168.1.100"
  port: number;       // e.g. 8000
  apiKey?: string;    // optional API key
  useTLS?: boolean;   // https/wss
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  tier?: number;
  intent?: string;
  mood?: string;
  timestamp: number;
  streaming?: boolean;
}

export interface VocaResponse {
  type: string;
  response: string;
  agent: string;
  tier: number;
  intent: string;
  needs_confirmation: boolean;
  mood: string;
}

type MessageHandler = (msg: VocaResponse) => void;
type StreamHandler = (token: string) => void;
type StreamEndHandler = (msg: VocaResponse) => void;
type ConnectionHandler = (connected: boolean) => void;

const buildBaseUrl = (config: ServerConfig, protocol: 'http' | 'ws') => {
  const scheme = config.useTLS ? `${protocol}s` : protocol;
  return `${scheme}://${config.host}:${config.port}`;
};

const buildAuthParams = (config: ServerConfig) => {
  return config.apiKey ? `?api_key=${encodeURIComponent(config.apiKey)}` : '';
};

// ─── REST API ────────────────────────────────────────────────

export async function fetchHealth(config: ServerConfig): Promise<boolean> {
  try {
    const url = `${buildBaseUrl(config, 'http')}/health`;
    const res = await fetch(url, { method: 'GET', headers: getHeaders(config) });
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}

export async function fetchAgents(config: ServerConfig) {
  const url = `${buildBaseUrl(config, 'http')}/agents${buildAuthParams(config)}`;
  const res = await fetch(url, { headers: getHeaders(config) });
  return res.json();
}

export async function fetchStatus(config: ServerConfig) {
  const url = `${buildBaseUrl(config, 'http')}/status${buildAuthParams(config)}`;
  const res = await fetch(url, { headers: getHeaders(config) });
  return res.json();
}

export async function sendChat(config: ServerConfig, transcript: string, sessionId?: string) {
  const url = `${buildBaseUrl(config, 'http')}/chat${buildAuthParams(config)}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...getHeaders(config), 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript, session_id: sessionId }),
  });
  return res.json();
}

function getHeaders(config: ServerConfig): Record<string, string> {
  const headers: Record<string, string> = {};
  if (config.apiKey) {
    headers['Authorization'] = `Bearer ${config.apiKey}`;
  }
  return headers;
}

// ─── WebSocket Client ────────────────────────────────────────

export class VocaWebSocket {
  private ws: WebSocket | null = null;
  private config: ServerConfig;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  onMessage: MessageHandler | null = null;
  onStreamToken: StreamHandler | null = null;
  onStreamEnd: StreamEndHandler | null = null;
  onConnection: ConnectionHandler | null = null;

  constructor(config: ServerConfig) {
    this.config = config;
  }

  connect() {
    const url = `${buildBaseUrl(this.config, 'ws')}/ws${buildAuthParams(this.config)}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('[VocaWS] Connected');
        this.reconnectAttempts = 0;
        this.onConnection?.(true);
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (e) {
          console.warn('[VocaWS] Parse error:', e);
        }
      };

      this.ws.onclose = (event) => {
        console.log('[VocaWS] Disconnected:', event.code, event.reason);
        this.onConnection?.(false);
        this.stopPing();
        if (event.code !== 4001) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (error) => {
        console.warn('[VocaWS] Error:', error);
      };
    } catch (e) {
      console.error('[VocaWS] Failed to connect:', e);
      this.scheduleReconnect();
    }
  }

  private handleMessage(data: any) {
    switch (data.type) {
      case 'response':
        this.onMessage?.(data as VocaResponse);
        break;
      case 'stream_token':
        this.onStreamToken?.(data.content);
        break;
      case 'stream_end':
        this.onStreamEnd?.(data as VocaResponse);
        break;
      case 'pong':
        break;
      case 'status':
        break;
      default:
        console.log('[VocaWS] Unknown message type:', data.type);
    }
  }

  send(transcript: string, stream: boolean = false) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[VocaWS] Not connected');
      return false;
    }
    this.ws.send(JSON.stringify({
      type: 'transcript',
      data: transcript,
      stream,
    }));
    return true;
  }

  confirm() {
    this.ws?.send(JSON.stringify({ type: 'confirm' }));
  }

  cancel() {
    this.send('no');
  }

  disconnect() {
    this.stopPing();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close(1000, 'User disconnect');
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  updateConfig(config: ServerConfig) {
    this.config = config;
    this.disconnect();
    this.reconnectAttempts = 0;
    this.connect();
  }

  private startPing() {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[VocaWS] Max reconnect attempts reached');
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    console.log(`[VocaWS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }
}
