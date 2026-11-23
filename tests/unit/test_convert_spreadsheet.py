"""convert_spreadsheet must not report success for a file it did not write.

``ConvertFormatTool`` wrote the output only for a lowercase ``.csv``,
``.xlsx`` or ``.json`` name and returned ``status: success`` for anything
else, so ``out.txt``, ``out.xls`` or ``OUT.JSON`` came back as converted
while no file was created.
"""

from __future__ import annotations

import json

import pytest

from vera.brain.agents.spreadsheet_agent import ConvertFormatTool

pytest.importorskip("pandas")


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text("name,age\nAda,36\nAlan,41\n", encoding="utf-8")
    return path


async def test_csv_to_json(csv_file, tmp_path):
    out = tmp_path / "people.json"
    result = await ConvertFormatTool().execute(input=str(csv_file), output=str(out))
    assert result["status"] == "success"
    assert result["rows"] == 2
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"name": "Ada", "age": 36},
        {"name": "Alan", "age": 41},
    ]


@pytest.mark.parametrize("name", ["people.txt", "people.xls", "people", "people.json.bak"])
async def test_unsupported_output_is_an_error(csv_file, tmp_path, name):
    out = tmp_path / name
    result = await ConvertFormatTool().execute(input=str(csv_file), output=str(out))
    assert result["status"] == "error"
    assert "Unsupported output format" in result["message"]
    assert not out.exists()


async def test_uppercase_output_extension_is_written(csv_file, tmp_path):
    out = tmp_path / "PEOPLE.JSON"
    result = await ConvertFormatTool().execute(input=str(csv_file), output=str(out))
    assert result["status"] == "success"
    assert out.exists()
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 2


async def test_uppercase_input_extension_is_read_as_csv(tmp_path):
    inp = tmp_path / "PEOPLE.CSV"
    inp.write_text("name,age\nAda,36\n", encoding="utf-8")
    out = tmp_path / "copy.csv"
    result = await ConvertFormatTool().execute(input=str(inp), output=str(out))
    assert result["status"] == "success"
    assert out.read_text(encoding="utf-8").splitlines() == ["name,age", "Ada,36"]
