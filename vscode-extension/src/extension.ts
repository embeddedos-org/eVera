/**
 * eVera AI — VS Code Extension
 * Connects to a local or remote eVera server and provides:
 *  - Inline chat sidebar
 *  - Explain / Fix / Generate / Review code actions
 *  - Model & mode switcher
 *  - RAG knowledge base file ingestion
 *  - Inline completions (Copilot-style)
 */

import * as vscode from "vscode";
import { EveraChatViewProvider } from "./chatViewProvider";
import { EveraModelsViewProvider } from "./modelsViewProvider";
import { EveraAgentsViewProvider } from "./agentsViewProvider";
import { EveraInlineCompletionProvider } from "./inlineCompletionProvider";
import { EveraApiClient } from "./apiClient";

let statusBarItem: vscode.StatusBarItem;
let apiClient: EveraApiClient;

export function activate(context: vscode.ExtensionContext) {
  console.log("[eVera] Extension activating...");

  // ── API client (shared across all providers) ──────────────────────────────
  const config = vscode.workspace.getConfiguration("evera");
  apiClient = new EveraApiClient(
    config.get<string>("serverUrl", "http://localhost:8765"),
    config.get<string>("apiKey", "")
  );

  // ── Status bar ─────────────────────────────────────────────────────────────
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = "evera.switchModel";
  updateStatusBar("auto", config.get<string>("mode", "local"));
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // ── Sidebar views ──────────────────────────────────────────────────────────
  const chatProvider = new EveraChatViewProvider(
    context.extensionUri,
    apiClient
  );
  const modelsProvider = new EveraModelsViewProvider(apiClient);
  const agentsProvider = new EveraAgentsViewProvider(apiClient);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("evera.chatView", chatProvider),
    vscode.window.registerTreeDataProvider("evera.modelsView", modelsProvider),
    vscode.window.registerTreeDataProvider("evera.agentsView", agentsProvider)
  );

  // ── Inline completions ─────────────────────────────────────────────────────
  if (config.get<boolean>("inlineCompletions", true)) {
    const inlineProvider = new EveraInlineCompletionProvider(apiClient);
    context.subscriptions.push(
      vscode.languages.registerInlineCompletionItemProvider(
        { pattern: "**" },
        inlineProvider
      )
    );
  }

  // ── Commands ───────────────────────────────────────────────────────────────

  // Open chat
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.chat", () => {
      vscode.commands.executeCommand("evera.chatView.focus");
    })
  );

  // Explain selected code
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.explainCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("eVera: Select some code first.");
        return;
      }
      const lang = editor.document.languageId;
      chatProvider.sendMessage(
        `Explain this ${lang} code in plain English:\n\`\`\`${lang}\n${code}\n\`\`\``
      );
      vscode.commands.executeCommand("evera.chatView.focus");
    })
  );

  // Fix selected code
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.fixCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const code = editor.document.getText(selection);
      if (!code.trim()) {
        vscode.window.showWarningMessage("eVera: Select some code first.");
        return;
      }
      const lang = editor.document.languageId;
      const result = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "eVera: Fixing code...",
          cancellable: false,
        },
        async () => {
          return await apiClient.chat(
            `Fix this ${lang} code. Return ONLY the corrected code, no explanation:\n\`\`\`${lang}\n${code}\n\`\`\``
          );
        }
      );
      if (result) {
        // Extract code block if wrapped in markdown
        const cleaned = extractCodeBlock(result);
        editor.edit((editBuilder) => {
          editBuilder.replace(selection, cleaned);
        });
        vscode.window.showInformationMessage("eVera: Code fixed!");
      }
    })
  );

  // Generate code from comment
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.generateCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const selection = editor.selection;
      const comment = editor.document.getText(selection);
      if (!comment.trim()) {
        vscode.window.showWarningMessage(
          "eVera: Select a comment or description first."
        );
        return;
      }
      const lang = editor.document.languageId;
      const result = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "eVera: Generating code...",
          cancellable: false,
        },
        async () => {
          return await apiClient.chat(
            `Generate ${lang} code for: ${comment}\nReturn ONLY the code, no explanation.`
          );
        }
      );
      if (result) {
        const cleaned = extractCodeBlock(result);
        editor.edit((editBuilder) => {
          // Insert after the selection
          editBuilder.insert(selection.end, "\n" + cleaned);
        });
      }
    })
  );

  // Review entire file
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.reviewCode", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const code = editor.document.getText();
      const lang = editor.document.languageId;
      const filename = editor.document.fileName.split("/").pop();
      chatProvider.sendMessage(
        `Review this ${lang} file (${filename}) for bugs, security issues, and improvements:\n\`\`\`${lang}\n${code.slice(0, 8000)}\n\`\`\``
      );
      vscode.commands.executeCommand("evera.chatView.focus");
    })
  );

  // Add file to knowledge base
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.addToKnowledge", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("eVera: Open a file first.");
        return;
      }
      const content = editor.document.getText();
      const filename = editor.document.fileName.split("/").pop() || "document";
      try {
        await apiClient.addToKnowledge(filename, content);
        vscode.window.showInformationMessage(
          `eVera: "${filename}" added to knowledge base!`
        );
      } catch (e) {
        vscode.window.showErrorMessage(`eVera: Failed to add to knowledge base: ${e}`);
      }
    })
  );

  // Switch model
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.switchModel", async () => {
      try {
        const models = await apiClient.getModels();
        const items = [
          { label: "$(sparkle) auto", description: "Virtual router — picks best model per task" },
          ...models.map((m: any) => ({
            label: m.id,
            description: `${m.offline ? "$(circle-filled) offline" : "$(cloud) cloud"} · ${m.description || ""}`,
          })),
        ];
        const picked = await vscode.window.showQuickPick(items, {
          placeHolder: "Select AI model for eVera",
          matchOnDescription: true,
        });
        if (picked) {
          const modelId = picked.label.replace("$(sparkle) ", "");
          await vscode.workspace
            .getConfiguration("evera")
            .update("model", modelId, true);
          apiClient.setModel(modelId);
          const mode = vscode.workspace
            .getConfiguration("evera")
            .get<string>("mode", "local");
          updateStatusBar(modelId, mode);
          vscode.window.showInformationMessage(`eVera: Model set to ${modelId}`);
        }
      } catch (e) {
        vscode.window.showErrorMessage(
          "eVera: Could not fetch models. Is the eVera server running?"
        );
      }
    })
  );

  // Switch mode
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.switchMode", async () => {
      const picked = await vscode.window.showQuickPick(
        [
          {
            label: "$(circle-filled) LOCAL",
            description: "Fully offline — no internet, no LAN",
          },
          {
            label: "$(broadcast) LAN",
            description: "Local network — access org data and other computers",
          },
          {
            label: "$(globe) WWW",
            description: "Full internet — all agents and cloud LLMs",
          },
        ],
        { placeHolder: "Select eVera operating mode" }
      );
      if (picked) {
        const modeMap: Record<string, string> = {
          "$(circle-filled) LOCAL": "local",
          "$(broadcast) LAN": "lan",
          "$(globe) WWW": "www",
        };
        const mode = modeMap[picked.label];
        await vscode.workspace
          .getConfiguration("evera")
          .update("mode", mode, true);
        await apiClient.setMode(mode);
        const model = vscode.workspace
          .getConfiguration("evera")
          .get<string>("model", "auto");
        updateStatusBar(model, mode);
        vscode.window.showInformationMessage(`eVera: Mode set to ${mode.toUpperCase()}`);
      }
    })
  );

  // Open dashboard
  context.subscriptions.push(
    vscode.commands.registerCommand("evera.openDashboard", () => {
      const serverUrl = vscode.workspace
        .getConfiguration("evera")
        .get<string>("serverUrl", "http://localhost:8765");
      vscode.env.openExternal(vscode.Uri.parse(serverUrl));
    })
  );

  // ── Config change listener ─────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("evera")) {
        const cfg = vscode.workspace.getConfiguration("evera");
        apiClient.updateConfig(
          cfg.get<string>("serverUrl", "http://localhost:8765"),
          cfg.get<string>("apiKey", "")
        );
        updateStatusBar(
          cfg.get<string>("model", "auto"),
          cfg.get<string>("mode", "local")
        );
      }
    })
  );

  console.log("[eVera] Extension activated.");
}

export function deactivate() {
  statusBarItem?.dispose();
}

function updateStatusBar(model: string, mode: string) {
  const modeIcon: Record<string, string> = {
    local: "$(circle-filled)",
    lan: "$(broadcast)",
    www: "$(globe)",
  };
  const icon = modeIcon[mode] || "$(circle-filled)";
  const shortModel = model === "auto" ? "auto" : model.split("/").pop()?.split(":")[0] || model;
  statusBarItem.text = `${icon} eVera · ${shortModel}`;
  statusBarItem.tooltip = `eVera AI — Mode: ${mode.toUpperCase()} · Model: ${model}\nClick to switch model`;
}

function extractCodeBlock(text: string): string {
  const match = text.match(/```(?:\w+)?\n([\s\S]*?)```/);
  return match ? match[1].trim() : text.trim();
}
