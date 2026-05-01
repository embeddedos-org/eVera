"""Spreadsheet Agent -- Excel/CSV operations, formulas, formatting."""

from __future__ import annotations

import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class CreateSpreadsheetTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_spreadsheet",
            description="Create Excel spreadsheet with data",
            parameters={
                "data": {"type": "str", "description": "JSON array of rows [{col:val}]"},
                "sheet_name": {"type": "str", "description": "Sheet name"},
                "output": {"type": "str", "description": "Output .xlsx path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import json

            import pandas as pd

            data = json.loads(kw.get("data", "[]")) if isinstance(kw.get("data"), str) else kw.get("data", [])
            df = pd.DataFrame(data)
            out = kw.get("output", "output.xlsx")
            df.to_excel(out, sheet_name=kw.get("sheet_name", "Sheet1"), index=False)
            return {"status": "success", "output": out, "rows": len(df), "columns": list(df.columns)}
        except ImportError:
            return {"status": "error", "message": "pip install pandas openpyxl"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ReadSpreadsheetTool(Tool):
    def __init__(self):
        super().__init__(
            name="read_spreadsheet",
            description="Read Excel/CSV spreadsheet",
            parameters={
                "file_path": {"type": "str", "description": "File path"},
                "sheet_name": {"type": "str", "description": "Sheet (optional)"},
                "range": {"type": "str", "description": "Cell range A1:D10 (optional)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pandas as pd

            fp = kw["file_path"]
            df = pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp, sheet_name=kw.get("sheet_name", 0))
            return {
                "status": "success",
                "rows": len(df),
                "columns": list(df.columns),
                "data": df.head(20).to_dict(orient="records"),
                "sheets": pd.ExcelFile(fp).sheet_names if fp.endswith((".xlsx", ".xls")) else ["Sheet1"],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class FormulaHelperTool(Tool):
    def __init__(self):
        super().__init__(
            name="formula_helper",
            description="Get Excel formula help and examples",
            parameters={
                "function": {"type": "str", "description": "Excel function name (VLOOKUP, IF, SUMIF, etc)"},
                "description": {"type": "str", "description": "What you want to calculate"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        formulas = {
            "VLOOKUP": "=VLOOKUP(lookup_value, table_array, col_index, [range_lookup])",
            "IF": "=IF(condition, value_if_true, value_if_false)",
            "SUMIF": "=SUMIF(range, criteria, [sum_range])",
            "COUNTIF": "=COUNTIF(range, criteria)",
            "INDEX": "=INDEX(array, row_num, [col_num])",
            "MATCH": "=MATCH(lookup_value, lookup_array, [match_type])",
            "CONCATENATE": "=CONCATENATE(text1, text2, ...)",
            "LEFT": "=LEFT(text, num_chars)",
            "RIGHT": "=RIGHT(text, num_chars)",
            "LEN": "=LEN(text)",
            "TRIM": "=TRIM(text)",
            "AVERAGE": "=AVERAGE(number1, number2, ...)",
            "MAX": "=MAX(number1, number2, ...)",
            "MIN": "=MIN(number1, number2, ...)",
        }
        fn = kw.get("function", "").upper()
        if fn in formulas:
            return {"status": "success", "function": fn, "syntax": formulas[fn]}
        return {"status": "success", "available": list(formulas.keys()), "tip": "Ask for any function by name"}


class ConvertFormatTool(Tool):
    def __init__(self):
        super().__init__(
            name="convert_spreadsheet",
            description="Convert between CSV/Excel/JSON formats",
            parameters={
                "input": {"type": "str", "description": "Input file path"},
                "output": {"type": "str", "description": "Output file path (.csv/.xlsx/.json)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import pandas as pd

            inp, out = kw["input"], kw["output"]
            df = (
                pd.read_csv(inp)
                if inp.endswith(".csv")
                else pd.read_excel(inp)
                if inp.endswith((".xlsx", ".xls"))
                else pd.read_json(inp)
            )
            if out.endswith(".csv"):
                df.to_csv(out, index=False)
            elif out.endswith(".xlsx"):
                df.to_excel(out, index=False)
            elif out.endswith(".json"):
                df.to_json(out, orient="records", indent=2)
            return {"status": "success", "input": inp, "output": out, "rows": len(df)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SpreadsheetAgent(BaseAgent):
    name = "spreadsheet"
    description = "Create/read/convert spreadsheets, Excel formulas help, CSV/Excel/JSON conversion"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Spreadsheet Agent. Create, read, convert spreadsheets, help with Excel formulas."
    offline_responses = {
        "excel": "\U0001f4ca Excel!",
        "spreadsheet": "\U0001f4ca Spreadsheet!",
        "csv": "\U0001f4c4 CSV!",
        "formula": "\U0001f522 Formula help!",
    }

    def _setup_tools(self):
        self._tools = [CreateSpreadsheetTool(), ReadSpreadsheetTool(), FormulaHelperTool(), ConvertFormatTool()]
