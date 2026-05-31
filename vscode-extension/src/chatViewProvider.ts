/**
 * eVera Chat Sidebar — WebviewViewProvider
 * Renders a full chat UI inside the VS Code sidebar.
 */

import * as vscode from "vscode";
import { EveraApiClient } from "./apiClient";

export class EveraChatViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "evera.chatView";
  private _view?: vscode.WebviewView;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _api: EveraApiClient
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };
    webviewView.webview.html = this._getHtml(webviewView.webview);

    // Handle messages from the webview
    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.type) {
        case "chat": {
          const userMsg = message.text as string;
          webviewView.webview.postMessage({
            type: "userMessage",
            text: userMsg,
          });
          try {
            // Try streaming first
            let fullResponse = "";
            webviewView.webview.postMessage({ type: "startStream" });
            try {
              for await (const token of this._api.chatStream(userMsg)) {
                fullResponse += token;
                webviewView.webview.postMessage({ type: "token", text: token });
              }
              webviewView.webview.postMessage({ type: "endStream" });
            } catch {
              // Fallback to non-streaming
              const response = await this._api.chat(userMsg);
              fullResponse = response;
              webviewView.webview.postMessage({
                type: "assistantMessage",
                text: response,
              });
            }
          } catch (e) {
            webviewView.webview.postMessage({
              type: "error",
              text: `eVera server not reachable. Make sure it's running at ${vscode.workspace.getConfiguration("evera").get("serverUrl")}.`,
            });
          }
          break;
        }
        case "openSettings": {
          vscode.commands.executeCommand(
            "workbench.action.openSettings",
            "evera"
          );
          break;
        }
        case "switchModel": {
          vscode.commands.executeCommand("evera.switchModel");
          break;
        }
        case "switchMode": {
          vscode.commands.executeCommand("evera.switchMode");
          break;
        }
        case "openDashboard": {
          vscode.commands.executeCommand("evera.openDashboard");
          break;
        }
      }
    });
  }

  /** Called externally (e.g. from code action commands) to pre-fill a message */
  public sendMessage(text: string) {
    this._view?.webview.postMessage({ type: "prefill", text });
  }

  private _getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';" />
  <title>eVera Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      background: var(--vscode-sideBar-background);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    #toolbar {
      display: flex;
      gap: 4px;
      padding: 6px 8px;
      border-bottom: 1px solid var(--vscode-sideBarSectionHeader-border);
      background: var(--vscode-sideBarSectionHeader-background);
      flex-shrink: 0;
    }
    #toolbar button {
      flex: 1;
      padding: 3px 6px;
      font-size: 11px;
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: none;
      border-radius: 3px;
      cursor: pointer;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    #toolbar button:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    #messages {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .msg {
      max-width: 100%;
      padding: 8px 10px;
      border-radius: 6px;
      line-height: 1.5;
      word-break: break-word;
      white-space: pre-wrap;
      font-size: 12px;
    }
    .msg.user {
      background: var(--vscode-inputValidation-infoBackground);
      border: 1px solid var(--vscode-inputValidation-infoBorder);
      align-self: flex-end;
      max-width: 85%;
    }
    .msg.assistant {
      background: var(--vscode-editor-inactiveSelectionBackground);
      border: 1px solid var(--vscode-widget-border);
      align-self: flex-start;
    }
    .msg.error {
      background: var(--vscode-inputValidation-errorBackground);
      border: 1px solid var(--vscode-inputValidation-errorBorder);
      color: var(--vscode-errorForeground);
    }
    .msg.streaming {
      border-style: dashed;
    }
    .cursor {
      display: inline-block;
      width: 2px;
      height: 14px;
      background: var(--vscode-foreground);
      animation: blink 1s step-end infinite;
      vertical-align: text-bottom;
      margin-left: 1px;
    }
    @keyframes blink { 50% { opacity: 0; } }
    #welcome {
      text-align: center;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      padding: 20px 8px;
    }
    #welcome h3 { font-size: 13px; margin-bottom: 6px; color: var(--vscode-foreground); }
    #welcome p { margin-bottom: 4px; }
    #input-area {
      display: flex;
      gap: 4px;
      padding: 8px;
      border-top: 1px solid var(--vscode-sideBarSectionHeader-border);
      background: var(--vscode-sideBar-background);
      flex-shrink: 0;
    }
    #input {
      flex: 1;
      padding: 6px 8px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      font-family: inherit;
      font-size: 12px;
      resize: none;
      min-height: 32px;
      max-height: 120px;
    }
    #input:focus { outline: 1px solid var(--vscode-focusBorder); }
    #send-btn {
      padding: 6px 10px;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      align-self: flex-end;
    }
    #send-btn:hover { background: var(--vscode-button-hoverBackground); }
    #send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    code {
      background: var(--vscode-textCodeBlock-background);
      padding: 1px 4px;
      border-radius: 3px;
      font-family: var(--vscode-editor-font-family);
      font-size: 11px;
    }
    pre {
      background: var(--vscode-textCodeBlock-background);
      padding: 8px;
      border-radius: 4px;
      overflow-x: auto;
      font-family: var(--vscode-editor-font-family);
      font-size: 11px;
      margin: 4px 0;
    }
  </style>
</head>
<body>
  <div id="toolbar">
    <button onclick="vscode.postMessage({type:'switchModel'})">⚡ Model</button>
    <button onclick="vscode.postMessage({type:'switchMode'})">🌐 Mode</button>
    <button onclick="vscode.postMessage({type:'openDashboard'})">📊 Dashboard</button>
    <button onclick="vscode.postMessage({type:'openSettings'})">⚙️</button>
  </div>
  <div id="messages">
    <div id="welcome">
      <h3>eVera AI</h3>
      <p>Your local-first AI agent.</p>
      <p>Ask anything, explain/fix code,<br>or run agents.</p>
      <p style="margin-top:8px;font-size:10px;opacity:0.7">Ctrl+Shift+X → Explain<br>Ctrl+Shift+F → Fix</p>
    </div>
  </div>
  <div id="input-area">
    <textarea id="input" placeholder="Ask eVera anything..." rows="1"></textarea>
    <button id="send-btn" title="Send (Enter)">➤</button>
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('send-btn');
    const welcomeEl = document.getElementById('welcome');
    let streamingEl = null;

    function addMessage(text, role) {
      if (welcomeEl) welcomeEl.remove();
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = text;
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return div;
    }

    function send() {
      const text = inputEl.value.trim();
      if (!text) return;
      inputEl.value = '';
      inputEl.style.height = 'auto';
      sendBtn.disabled = true;
      vscode.postMessage({ type: 'chat', text });
    }

    sendBtn.addEventListener('click', send);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      switch (msg.type) {
        case 'userMessage':
          addMessage(msg.text, 'user');
          break;
        case 'startStream':
          streamingEl = addMessage('', 'assistant streaming');
          streamingEl.innerHTML = '<span class="cursor"></span>';
          break;
        case 'token':
          if (streamingEl) {
            const cursor = streamingEl.querySelector('.cursor');
            const text = document.createTextNode(msg.text);
            if (cursor) streamingEl.insertBefore(text, cursor);
            else streamingEl.appendChild(text);
            messagesEl.scrollTop = messagesEl.scrollHeight;
          }
          break;
        case 'endStream':
          if (streamingEl) {
            streamingEl.classList.remove('streaming');
            const cursor = streamingEl.querySelector('.cursor');
            if (cursor) cursor.remove();
            streamingEl = null;
          }
          sendBtn.disabled = false;
          break;
        case 'assistantMessage':
          addMessage(msg.text, 'assistant');
          sendBtn.disabled = false;
          break;
        case 'error':
          addMessage(msg.text, 'error');
          sendBtn.disabled = false;
          break;
        case 'prefill':
          if (welcomeEl) welcomeEl.remove();
          inputEl.value = msg.text;
          inputEl.style.height = 'auto';
          inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
          inputEl.focus();
          break;
      }
    });
  </script>
</body>
</html>`;
  }
}

function getNonce(): string {
  let text = "";
  const possible =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
