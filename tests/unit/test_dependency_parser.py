"""Unit tests for the code dependency graph parser.

Covers vera/brain/tools/dependency_parser.py, which backs
GET /api/code/dependency-graph. A Python file's node "contains" its
classes and its module-level functions; methods belong to their class
and must not be listed as functions of the file.
"""

from __future__ import annotations

from pathlib import Path

from vera.brain.tools.dependency_parser import parse_dependencies

SOURCE = """\
class Shape:
    def area(self):
        return 0

    async def refresh(self):
        return None


def make_shape():
    return Shape()


async def load_shapes():
    return [make_shape()]
"""


def _graph(tmp_path: Path) -> dict:
    (tmp_path / "shapes.py").write_text(SOURCE)
    return parse_dependencies(str(tmp_path))


def _ids(graph: dict, node_type: str) -> set[str]:
    return {n["id"] for n in graph["nodes"] if n["type"] == node_type}


def test_module_level_functions_are_listed(tmp_path):
    graph = _graph(tmp_path)
    functions = _ids(graph, "function")
    assert "shapes_py__fn_make_shape" in functions
    assert "shapes_py__fn_load_shapes" in functions


def test_class_is_listed_and_contained_by_its_file(tmp_path):
    graph = _graph(tmp_path)
    assert "shapes_py__class_Shape" in _ids(graph, "class")
    assert {"source": "shapes_py", "target": "shapes_py__class_Shape", "type": "contains"} in graph["edges"]


def test_methods_are_not_listed_as_file_functions(tmp_path):
    graph = _graph(tmp_path)
    assert _ids(graph, "function") == {"shapes_py__fn_make_shape", "shapes_py__fn_load_shapes"}
    contained = {e["target"] for e in graph["edges"] if e["source"] == "shapes_py" and e["type"] == "contains"}
    assert contained == {
        "shapes_py__class_Shape",
        "shapes_py__fn_make_shape",
        "shapes_py__fn_load_shapes",
    }


COMPOUND_SOURCE = """\
class Shape:
    if True:
        def area(self):
            return 0

    try:
        def maybe(self):
            return 1
    except Exception:
        def fallback(self):
            return 2

    def outer(self):
        def inner():
            return 3
        return inner


def make_shape():
    return Shape()
"""


def test_class_body_compound_methods_are_not_listed_as_file_functions(tmp_path):
    (tmp_path / "shapes.py").write_text(COMPOUND_SOURCE)
    graph = parse_dependencies(str(tmp_path))
    functions = _ids(graph, "function")
    assert "shapes_py__fn_make_shape" in functions
    assert "shapes_py__fn_area" not in functions
    assert "shapes_py__fn_maybe" not in functions
    assert "shapes_py__fn_fallback" not in functions
    contained = {
        e["target"]
        for e in graph["edges"]
        if e["source"] == "shapes_py" and e["type"] == "contains"
    }
    assert "shapes_py__class_Shape" in contained
    assert "shapes_py__fn_area" not in contained
    assert "shapes_py__fn_maybe" not in contained
    assert "shapes_py__fn_fallback" not in contained
