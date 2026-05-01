"""Data Analyst Agent -- analysis, visualization, ML training, SQL queries.

Surpasses GPT-4o Code Interpreter with pandas, matplotlib, seaborn,
scikit-learn, DuckDB SQL, pivot tables, and data cleaning.
"""

from __future__ import annotations

import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class LoadDataTool(Tool):
    """Load data from CSV/Excel/JSON/Parquet."""

    def __init__(self):
        super().__init__(
            name="load_data",
            description="Load CSV/Excel/JSON/Parquet into DataFrame",
            parameters={
                "file_path": {"type": "str", "description": "Data file path"},
                "sheet_name": {"type": "str", "description": "Excel sheet (optional)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        fp = kw.get("file_path", "")
        try:
            import pandas as pd

            if fp.endswith(".csv"):
                df = pd.read_csv(fp)
            elif fp.endswith((".xlsx", ".xls")):
                df = pd.read_excel(fp)
            elif fp.endswith(".json"):
                df = pd.read_json(fp)
            elif fp.endswith(".parquet"):
                df = pd.read_parquet(fp)
            else:
                return {"status": "error", "message": "Unsupported format"}
            return {
                "status": "success",
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
                "preview": df.head(5).to_dict(orient="records"),
            }
        except ImportError:
            return {"status": "error", "message": "pip install pandas openpyxl"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AnalyzeDataTool(Tool):
    """Perform statistical analysis on a dataset."""

    def __init__(self):
        super().__init__(
            name="analyze_data",
            description="Statistical analysis (describe/correlation/distribution/outliers/missing)",
            parameters={
                "file_path": {"type": "str", "description": "Data file"},
                "analysis_type": {"type": "str", "description": "describe|correlation|distribution|outliers|missing"},
                "column": {"type": "str", "description": "Column name"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        fp, at, col = kw.get("file_path", ""), kw.get("analysis_type", "describe"), kw.get("column", "")
        try:
            import numpy as np
            import pandas as pd

            df = pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp)
            if at == "describe":
                return {"status": "success", "stats": df.describe().to_dict()}
            elif at == "correlation":
                return {"status": "success", "corr": df.select_dtypes(include=[np.number]).corr().round(3).to_dict()}
            elif at == "distribution" and col:
                c = df[col]
                return {
                    "status": "success",
                    "mean": float(c.mean()),
                    "median": float(c.median()),
                    "std": float(c.std()),
                    "min": float(c.min()),
                    "max": float(c.max()),
                }
            elif at == "outliers":
                n = df.select_dtypes(include=[np.number])
                Q1, Q3 = n.quantile(0.25), n.quantile(0.75)
                IQR = Q3 - Q1
                return {
                    "status": "success",
                    "outliers": ((n < (Q1 - 1.5 * IQR)) | (n > (Q3 + 1.5 * IQR))).sum().to_dict(),
                }
            elif at == "missing":
                m = df.isnull().sum()
                return {"status": "success", "missing": m.to_dict(), "pct": (m / len(df) * 100).round(2).to_dict()}
            return {"status": "error", "message": "Specify analysis_type"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class VisualizeTool(Tool):
    """Create data visualizations."""

    def __init__(self):
        super().__init__(
            name="visualize_data",
            description="Create charts (bar/line/scatter/pie/histogram/heatmap/box)",
            parameters={
                "file_path": {"type": "str", "description": "Data file"},
                "chart_type": {"type": "str", "description": "bar|line|scatter|pie|histogram|heatmap|box"},
                "x_column": {"type": "str", "description": "X column"},
                "y_column": {"type": "str", "description": "Y column"},
                "title": {"type": "str", "description": "Chart title"},
                "output": {"type": "str", "description": "Output image path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        fp, ct, xc, yc = (
            kw.get("file_path", ""),
            kw.get("chart_type", "bar"),
            kw.get("x_column", ""),
            kw.get("y_column", ""),
        )
        out = kw.get("output", "chart.png")
        try:
            import pandas as pd
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns

            df = pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp)
            fig, ax = plt.subplots(figsize=(12, 8))
            sns.set_theme(style="whitegrid")
            if ct == "bar":
                sns.barplot(data=df, x=xc, y=yc, ax=ax)
            elif ct == "line":
                sns.lineplot(data=df, x=xc, y=yc, ax=ax)
            elif ct == "scatter":
                sns.scatterplot(data=df, x=xc, y=yc, ax=ax)
            elif ct == "pie":
                df[xc].value_counts().head(10).plot.pie(ax=ax, autopct="%1.1f%%")
            elif ct == "histogram":
                sns.histplot(data=df, x=xc or yc, ax=ax, kde=True)
            elif ct == "heatmap":
                import numpy as np

                sns.heatmap(df.select_dtypes(include=[np.number]).corr(), annot=True, cmap="coolwarm", ax=ax)
            elif ct == "box":
                sns.boxplot(data=df, x=xc, y=yc, ax=ax)
            ax.set_title(kw.get("title", "Visualization"), fontsize=16)
            plt.tight_layout()
            plt.savefig(out, dpi=150)
            plt.close()
            return {"status": "success", "chart_type": ct, "output": out}
        except ImportError:
            return {"status": "error", "message": "pip install pandas matplotlib seaborn"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CleanDataTool(Tool):
    """Clean and transform data."""

    def __init__(self):
        super().__init__(
            name="clean_data",
            description="Clean data: drop/fill NaN, remove duplicates",
            parameters={
                "file_path": {"type": "str", "description": "Data file"},
                "action": {"type": "str", "description": "drop_na|fill_na|drop_duplicates"},
                "column": {"type": "str", "description": "Column"},
                "fill_value": {"type": "str", "description": "Fill value"},
                "output": {"type": "str", "description": "Output path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        fp, action, col = kw.get("file_path", ""), kw.get("action", "drop_na"), kw.get("column", "")
        try:
            import pandas as pd

            df = pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp)
            orig = df.shape
            if action == "drop_na":
                df = df.dropna(subset=[col] if col else None)
            elif action == "fill_na":
                if col:
                    df[col] = df[col].fillna(kw.get("fill_value", "0"))
                else:
                    df = df.fillna(kw.get("fill_value", "0"))
            elif action == "drop_duplicates":
                df = df.drop_duplicates(subset=[col] if col else None)
            out = kw.get("output", "cleaned.csv")
            df.to_csv(out, index=False)
            return {"status": "success", "original": list(orig), "cleaned": list(df.shape), "output": out}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TrainModelTool(Tool):
    """Train ML models on data."""

    def __init__(self):
        super().__init__(
            name="train_model",
            description="Train ML model (random_forest/gradient_boost/linear/logistic/decision_tree)",
            parameters={
                "file_path": {"type": "str", "description": "Training data"},
                "target_column": {"type": "str", "description": "Target column"},
                "model_type": {
                    "type": "str",
                    "description": "random_forest|gradient_boost|linear|logistic|decision_tree",
                },
                "test_size": {"type": "float", "description": "Test split (default 0.2)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        fp, target, mt = kw.get("file_path", ""), kw.get("target_column", ""), kw.get("model_type", "random_forest")
        try:
            import numpy as np
            import pandas as pd
            from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
            from sklearn.model_selection import train_test_split

            df = pd.read_csv(fp)
            X = df.drop(columns=[target]).select_dtypes(include=[np.number])
            y = df[target]
            Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=kw.get("test_size", 0.2), random_state=42)
            is_cls = y.nunique() < 20
            if mt == "random_forest":
                from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

                model = (
                    RandomForestClassifier(n_estimators=100, random_state=42)
                    if is_cls
                    else RandomForestRegressor(n_estimators=100, random_state=42)
                )
            elif mt == "gradient_boost":
                from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

                model = (
                    GradientBoostingClassifier(random_state=42)
                    if is_cls
                    else GradientBoostingRegressor(random_state=42)
                )
            elif mt == "logistic":
                from sklearn.linear_model import LogisticRegression

                model = LogisticRegression(max_iter=1000)
            elif mt == "decision_tree":
                from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

                model = DecisionTreeClassifier(random_state=42) if is_cls else DecisionTreeRegressor(random_state=42)
            else:
                from sklearn.linear_model import LinearRegression

                model = LinearRegression()
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            metrics = (
                {"accuracy": round(accuracy_score(yte, pred), 4)}
                if is_cls
                else {
                    "rmse": round(float(np.sqrt(mean_squared_error(yte, pred))), 4),
                    "r2": round(float(r2_score(yte, pred)), 4),
                }
            )
            fi = (
                dict(zip(X.columns, [round(float(x), 4) for x in model.feature_importances_]))
                if hasattr(model, "feature_importances_")
                else {}
            )
            return {
                "status": "success",
                "model": mt,
                "task": "classification" if is_cls else "regression",
                "metrics": metrics,
                "feature_importance": fi,
            }
        except ImportError:
            return {"status": "error", "message": "pip install scikit-learn pandas"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PivotTableTool(Tool):
    """Create pivot tables."""

    def __init__(self):
        super().__init__(
            name="pivot_table",
            description="Create pivot table",
            parameters={
                "file_path": {"type": "str", "description": "Data file"},
                "index": {"type": "str", "description": "Row grouping"},
                "columns": {"type": "str", "description": "Column grouping"},
                "values": {"type": "str", "description": "Values column"},
                "aggfunc": {"type": "str", "description": "mean|sum|count|min|max"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pandas as pd

            fp = kw["file_path"]
            df = pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp)
            pivot = pd.pivot_table(
                df,
                index=kw.get("index"),
                columns=kw.get("columns") or None,
                values=kw.get("values") or None,
                aggfunc=kw.get("aggfunc", "mean"),
            )
            return {"status": "success", "pivot": pivot.head(20).to_dict(), "shape": list(pivot.shape)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SQLQueryTool(Tool):
    """Run SQL queries on data files via DuckDB."""

    def __init__(self):
        super().__init__(
            name="sql_query",
            description="Run SQL on CSV/Parquet via DuckDB",
            parameters={
                "query": {"type": "str", "description": "SQL query"},
                "file_path": {"type": "str", "description": "Data file"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import duckdb

            conn = duckdb.connect()
            fp = kw.get("file_path", "")
            q = kw["query"]
            if fp:
                conn.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{fp}')")
                q = q.replace(fp, "data")
            result = conn.execute(q).fetchdf()
            return {
                "status": "success",
                "rows": len(result),
                "columns": list(result.columns),
                "data": result.head(50).to_dict(orient="records"),
            }
        except ImportError:
            return {"status": "error", "message": "pip install duckdb"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class DataAnalystAgent(BaseAgent):
    """Full-spectrum data analysis, visualization, ML, and SQL."""

    name = "data_analyst"
    description = "Data analysis, visualization, ML training, SQL queries, data cleaning, pivot tables"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Data Analyst. Load datasets, run statistics, create visualizations, train ML models, create pivot tables, run SQL queries on files."
    offline_responses = {
        "analyze": "\U0001f4ca Analyzing!",
        "chart": "\U0001f4c8 Creating chart!",
        "data": "\U0001f4ca Looking at data!",
        "train": "\U0001f916 Training model!",
    }

    def _setup_tools(self):
        self._tools = [
            LoadDataTool(),
            AnalyzeDataTool(),
            VisualizeTool(),
            CleanDataTool(),
            TrainModelTool(),
            PivotTableTool(),
            SQLQueryTool(),
        ]
