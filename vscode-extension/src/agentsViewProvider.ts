import * as vscode from "vscode";
import { EveraApiClient } from "./apiClient";

export class AgentItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly description: string,
    public readonly collapsibleState = vscode.TreeItemCollapsibleState.None
  ) {
    super(label, collapsibleState);
    this.tooltip = description;
    this.iconPath = new vscode.ThemeIcon("robot");
  }
}

export class EveraAgentsViewProvider
  implements vscode.TreeDataProvider<AgentItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<AgentItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly _api: EveraApiClient) {}

  refresh() {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: AgentItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<AgentItem[]> {
    try {
      const agents = await this._api.getAgents();
      const list = Array.isArray(agents) ? agents : Object.keys(agents);
      return list.slice(0, 60).map((a: any) => {
        const name = typeof a === "string" ? a : a.name || a.id || String(a);
        const desc = typeof a === "object" ? a.description || a.role || "" : "";
        return new AgentItem(name, desc);
      });
    } catch {
      return [new AgentItem("Server not reachable", "Start eVera server first")];
    }
  }
}
