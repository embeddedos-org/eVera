"""Tests for workflow engine — create, execute, conditions, templates."""

from __future__ import annotations

import pytest


@pytest.fixture
def workflow_engine(tmp_path):
    import voca.brain.workflow as wf_mod
    wf_mod.WORKFLOWS_DIR = tmp_path / "workflows"
    from voca.brain.workflow import WorkflowEngine
    return WorkflowEngine()


class TestWorkflowEngine:
    def test_create_workflow(self, workflow_engine):
        wf = workflow_engine.create({
            "name": "test_workflow",
            "description": "A test",
            "steps": [
                {"id": "1", "type": "notify", "message": "Hello!"},
            ],
        })
        assert wf.name == "test_workflow"
        assert len(wf.steps) == 1

    def test_list_workflows(self, workflow_engine):
        workflow_engine.create({"name": "wf1", "steps": []})
        workflow_engine.create({"name": "wf2", "steps": []})
        result = workflow_engine.list_all()
        assert len(result) == 2

    def test_delete_workflow(self, workflow_engine):
        workflow_engine.create({"name": "to_delete", "steps": []})
        assert workflow_engine.delete("to_delete") is True
        assert workflow_engine.get("to_delete") is None

    def test_template_resolution(self, workflow_engine):
        resolved = workflow_engine._resolve_template_string(
            "Hello {{vars.name}}, result is {{steps.1.output}}",
            {"1": {"output": "42"}},
            {"name": "Alice"},
        )
        assert "Alice" in resolved
        assert "42" in resolved

    def test_workflow_persistence(self, workflow_engine):
        workflow_engine.create({
            "name": "persistent",
            "steps": [{"id": "1", "type": "notify", "message": "saved"}],
        })
        # Reload
        import voca.brain.workflow as wf_mod
        engine2 = wf_mod.WorkflowEngine()
        assert engine2.get("persistent") is not None
