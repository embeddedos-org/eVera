/**
 * eVera Inline Completion Provider — Copilot-style code completions.
 * Triggered after a pause in typing. Sends the last 2000 chars of context
 * to eVera and returns a single completion suggestion.
 */

import * as vscode from "vscode";
import { EveraApiClient } from "./apiClient";

export class EveraInlineCompletionProvider
  implements vscode.InlineCompletionItemProvider
{
  private _lastRequestTime = 0;
  private _debounceMs = 600;

  constructor(private readonly _api: EveraApiClient) {}

  async provideInlineCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    _context: vscode.InlineCompletionContext,
    token: vscode.CancellationToken
  ): Promise<vscode.InlineCompletionList | null> {
    // Debounce
    const now = Date.now();
    if (now - this._lastRequestTime < this._debounceMs) return null;
    this._lastRequestTime = now;

    // Only complete on non-empty lines or after specific triggers
    const linePrefix = document.lineAt(position).text.slice(0, position.character);
    if (!linePrefix.trim()) return null;

    // Get context: up to 2000 chars before cursor
    const docText = document.getText();
    const offset = document.offsetAt(position);
    const contextBefore = docText.slice(Math.max(0, offset - 2000), offset);
    const lang = document.languageId;

    if (token.isCancellationRequested) return null;

    try {
      const prompt = `Complete the following ${lang} code. Return ONLY the completion (no explanation, no markdown, no code fences). Continue from exactly where it left off:\n${contextBefore}`;
      const completion = await this._api.chat(prompt, "vscode-inline");

      if (token.isCancellationRequested) return null;
      if (!completion?.trim()) return null;

      // Clean up: remove any accidental code fences
      const cleaned = completion
        .replace(/^```[\w]*\n?/, "")
        .replace(/\n?```$/, "")
        .trim();

      return {
        items: [
          new vscode.InlineCompletionItem(
            cleaned,
            new vscode.Range(position, position)
          ),
        ],
      };
    } catch {
      return null;
    }
  }
}
