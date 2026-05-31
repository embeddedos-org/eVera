import * as vscode from "vscode";
import { EveraApiClient } from "./apiClient";

export class ModelItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly description: string,
    public readonly offline: boolean,
    public readonly collapsibleState = vscode.TreeItemCollapsibleState.None
  ) {
    super(label, collapsibleState);
    this.tooltip = description;
    this.iconPath = new vscode.ThemeIcon(offline ? "circle-filled" : "cloud");
    this.contextValue = "model";
    this.command = {
      command: "evera.switchModel",
      title: "Select Model",
    };
  }
}

export class EveraModelsViewProvider
  implements vscode.TreeDataProvider<ModelItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<ModelItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly _api: EveraApiClient) {}

  refresh() {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ModelItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<ModelItem[]> {
    try {
      const models = await this._api.getModels();
      return models.slice(0, 50).map(
        (m: any) =>
          new ModelItem(
            m.id || m.name,
            m.description || "",
            m.offline ?? false
          )
      );
    } catch {
      return [
        new ModelItem(
          "Server not reachable",
          "Start eVera server first",
          false
        ),
      ];
    }
  }
}
