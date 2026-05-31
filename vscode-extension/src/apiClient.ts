/**
 * eVera API Client — communicates with the eVera server from VS Code.
 */

export class EveraApiClient {
  private serverUrl: string;
  private apiKey: string;
  private model: string = "auto";

  constructor(serverUrl: string, apiKey: string) {
    this.serverUrl = serverUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  updateConfig(serverUrl: string, apiKey: string) {
    this.serverUrl = serverUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  setModel(model: string) {
    this.model = model;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) h["Authorization"] = `Bearer ${this.apiKey}`;
    return h;
  }

  async chat(message: string, sessionId?: string): Promise<string> {
    const resp = await fetch(`${this.serverUrl}/api/chat`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        transcript: message,
        session_id: sessionId || "vscode",
        model_override: this.model !== "auto" ? this.model : undefined,
      }),
    });
    if (!resp.ok) throw new Error(`eVera server error: ${resp.status}`);
    const data = await resp.json() as any;
    return data.response || data.text || JSON.stringify(data);
  }

  async *chatStream(
    message: string,
    sessionId?: string
  ): AsyncGenerator<string> {
    const resp = await fetch(`${this.serverUrl}/api/chat/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        transcript: message,
        session_id: sessionId || "vscode",
        model_override: this.model !== "auto" ? this.model : undefined,
      }),
    });
    if (!resp.ok || !resp.body) {
      throw new Error(`eVera stream error: ${resp.status}`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") return;
          try {
            const obj = JSON.parse(payload);
            if (obj.token) yield obj.token;
          } catch {
            // non-JSON line, skip
          }
        }
      }
    }
  }

  async getModels(): Promise<any[]> {
    const resp = await fetch(`${this.serverUrl}/api/models`, {
      headers: this.headers(),
    });
    if (!resp.ok) throw new Error(`eVera: ${resp.status}`);
    const data = await resp.json() as any;
    return data.models || data || [];
  }

  async getAgents(): Promise<any[]> {
    const resp = await fetch(`${this.serverUrl}/agents`, {
      headers: this.headers(),
    });
    if (!resp.ok) throw new Error(`eVera: ${resp.status}`);
    const data = await resp.json() as any;
    return data.agents || data || [];
  }

  async setMode(mode: string): Promise<void> {
    await fetch(`${this.serverUrl}/mode`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ mode }),
    });
  }

  async getHealth(): Promise<any> {
    const resp = await fetch(`${this.serverUrl}/health`, {
      headers: this.headers(),
    });
    return resp.json();
  }

  async addToKnowledge(filename: string, content: string): Promise<any> {
    const resp = await fetch(`${this.serverUrl}/knowledge/ingest`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ filename, content, source: "vscode" }),
    });
    if (!resp.ok) throw new Error(`eVera knowledge error: ${resp.status}`);
    return resp.json();
  }
}
