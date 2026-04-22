"""Diagram Agent — generates code visualizations (call graphs, class diagrams, flowcharts).

@file vera/brain/agents/diagram_agent.py
@brief DiagramAgent uses AST-based tools to generate Mermaid diagrams from source code.
"""

from __future__ import annotations

from vera.brain.agents.base import BaseAgent
from vera.brain.agents.diagram_tools import (
    ExportDiagramTool,
    GenerateCallGraphTool,
    GenerateClassDiagramTool,
    GenerateFlowchartTool,
)
from vera.providers.models import ModelTier


class DiagramAgent(BaseAgent):
    """Agent for generating code visualization diagrams."""

    name = "diagram"
    description = (
        "Generates code visualizations: call graphs, class diagrams, flowcharts, and exports them as SVG/PNG/PDF."
    )
    tier = ModelTier.SPECIALIST

    system_prompt = (
        "You are a code visualization specialist. You help users understand "
        "code structure by generating clear, informative diagrams.\n\n"
        "CAPABILITIES:\n"
        "- Generate call graphs showing function call relationships\n"
        "- Generate class diagrams showing inheritance and methods\n"
        "- Generate flowcharts showing control flow within functions\n"
        "- Export diagrams to SVG, PNG, or PDF\n\n"
        "When the user asks for a diagram, determine the best tool to use "
        "and generate the visualization. Always return the Mermaid markup "
        "in a ```mermaid code block so it can be rendered in the UI.\n\n"
        "If the user provides a project path, use it directly. "
        "If not, ask them which project or file they want to visualize."
    )

    offline_responses = {
        "diagram": "I can generate diagrams! 📊 Tell me what you'd like — a call graph, class diagram, or flowchart. I'll need the project or file path!",
        "call_graph": "I can generate a call graph! 📊 Just tell me the project path and I'll map out the function calls.",
        "class_diagram": "I can generate a class diagram! 🏗️ Give me the project path and I'll show the class hierarchy.",
        "flowchart": "I can generate a flowchart! 📋 Tell me the file and function name and I'll visualize the control flow.",
        "visualize": "I'm your code visualization buddy! 📊 I can create call graphs, class diagrams, and flowcharts. What would you like?",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            GenerateCallGraphTool(),
            GenerateClassDiagramTool(),
            GenerateFlowchartTool(),
            ExportDiagramTool(),
        ]
