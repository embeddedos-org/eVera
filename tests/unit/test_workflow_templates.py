"""Workflow template resolution: {{steps.N.output}} is the output of step N.

The engine stores each step's result as-is in ``step_outputs[step.id]``
and the module docstring passes it on with ``{{steps.1.output}}``. Most
results are dicts (agent tools, the natural-language fallback, notify
steps), so the template must not look for an "output" key inside them.
"""

from __future__ import annotations

import pytest

import vera.brain.workflow as workflow_mod
from vera.brain.workflow import WorkflowEngine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_mod, "WORKFLOWS_DIR", tmp_path / "workflows")
    return WorkflowEngine()


def test_step_output_is_the_whole_dict_result(engine):
    outputs = {"1": {"response": "tech news", "agent": "researcher"}}
    resolved = engine._resolve_template_string("{{steps.1.output}}", outputs, {})
    assert resolved == str(outputs["1"])


def test_step_output_field_of_a_dict_result(engine):
    outputs = {"1": {"response": "tech news", "agent": "researcher"}}
    resolved = engine._resolve_template_string("Topic: {{steps.1.output.response}}", outputs, {})
    assert resolved == "Topic: tech news"


def test_step_output_of_a_string_result(engine):
    resolved = engine._resolve_template_string("{{steps.1.output}}", {"1": "plain text"}, {})
    assert resolved == "plain text"


def test_template_params_resolve_step_output_field(engine):
    params = {"body": "{{steps.2.output.response}}", "to": "me@example.com", "count": 3}
    outputs = {"2": {"response": "Draft text", "agent": "writer"}}
    assert engine._resolve_templates(params, outputs, {}) == {
        "body": "Draft text",
        "to": "me@example.com",
        "count": 3,
    }


def test_unknown_step_is_left_as_is(engine):
    assert engine._resolve_template_string("{{steps.9.output}}", {}, {}) == "{{steps.9.output}}"


async def test_notify_step_sees_previous_step_output(engine):
    engine.create(
        {
            "name": "chain",
            "steps": [
                {"id": "1", "type": "notify", "message": "first message"},
                {
                    "id": "2",
                    "type": "notify",
                    "message": "Got: {{steps.1.output.message}}",
                    "depends_on": ["1"],
                },
            ],
        }
    )
    result = await engine.execute("chain", brain=None)
    assert result["steps_failed"] == 0
    assert result["results"]["2"]["message"] == "Got: first message"
