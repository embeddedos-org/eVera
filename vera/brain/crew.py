"""Multi-agent orchestration — CrewAI/AutoGen-style collaboration.

Enables complex tasks to be decomposed and delegated across multiple agents
working together with shared context.

Usage:
    crew = Crew(
        task="Research AI trends and write a blog post about them",
        agents=["researcher", "writer"],
        strategy="sequential",  # or "parallel", "debate", "hierarchical"
    )
    result = await crew.execute(brain)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """A sub-task assigned to a specific agent."""

    id: str
    agent_name: str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrewResult:
    """Result of a multi-agent crew execution."""

    final_response: str
    tasks: list[AgentTask]
    strategy: str
    total_time_ms: float
    agents_used: list[str]


class TaskDecomposer:
    """Decomposes complex tasks into agent-specific sub-tasks using LLM."""

    DECOMPOSITION_PROMPT = """You are a task decomposition expert. Break down the user's complex request into sub-tasks, each assigned to the most appropriate agent.

Available agents:
{agents}

User request: {task}

Respond with ONLY a JSON array of sub-tasks:
[
  {{"id": "1", "agent": "agent_name", "instruction": "specific instruction", "depends_on": []}},
  {{"id": "2", "agent": "agent_name", "instruction": "specific instruction", "depends_on": ["1"]}}
]

Rules:
- Use depends_on to specify which tasks must complete first
- Tasks with no dependencies can run in parallel
- Keep instructions specific and actionable
- Use the agent best suited for each sub-task
"""

    @staticmethod
    async def decompose(task: str, available_agents: dict, provider_manager: Any) -> list[AgentTask]:
        """Break down a complex task into agent-specific sub-tasks."""
        agents_desc = "\n".join(
            f"- {name}: {agent.description} (tools: {', '.join(t.name for t in agent.tools)})"
            for name, agent in available_agents.items()
        )

        prompt = TaskDecomposer.DECOMPOSITION_PROMPT.format(
            agents=agents_desc, task=task,
        )

        try:
            from vera.providers.models import ModelTier
            result = await provider_manager.complete(
                messages=[{"role": "user", "content": prompt}],
                tier=ModelTier.SPECIALIST,
            )

            # Parse JSON from response
            text = result.content.strip()
            # Extract JSON array from response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                tasks_data = json.loads(text[start:end])
            else:
                tasks_data = json.loads(text)

            return [
                AgentTask(
                    id=str(t.get("id", i)),
                    agent_name=t.get("agent", "companion"),
                    instruction=t.get("instruction", ""),
                    depends_on=t.get("depends_on", []),
                )
                for i, t in enumerate(tasks_data)
            ]
        except Exception as e:
            logger.warning("Task decomposition failed: %s — using single agent", e)
            return [AgentTask(id="1", agent_name="companion", instruction=task)]


class Crew:
    """A crew of agents collaborating on a complex task."""

    STRATEGIES = ("sequential", "parallel", "hierarchical", "debate")

    def __init__(
        self,
        task: str,
        agents: list[str] | None = None,
        strategy: str = "sequential",
        max_rounds: int = 3,
    ) -> None:
        self.task = task
        self.agent_names = agents
        self.strategy = strategy if strategy in self.STRATEGIES else "sequential"
        self.max_rounds = max_rounds
        self.tasks: list[AgentTask] = []

    async def execute(self, brain: Any) -> CrewResult:
        """Execute the crew task using the selected strategy."""
        import time
        start = time.monotonic()

        from vera.brain.agents import AGENT_REGISTRY

        # Filter available agents
        if self.agent_names:
            available = {k: v for k, v in AGENT_REGISTRY.items() if k in self.agent_names}
        else:
            available = AGENT_REGISTRY

        # Decompose task into sub-tasks
        self.tasks = await TaskDecomposer.decompose(
            self.task, available, brain.provider_manager,
        )

        # Execute based on strategy
        if self.strategy == "parallel":
            await self._execute_parallel(brain)
        elif self.strategy == "hierarchical":
            await self._execute_hierarchical(brain)
        elif self.strategy == "debate":
            await self._execute_debate(brain)
        else:
            await self._execute_sequential(brain)

        # Synthesize final response
        final = self._synthesize_results()

        elapsed = (time.monotonic() - start) * 1000
        agents_used = list(set(t.agent_name for t in self.tasks))

        return CrewResult(
            final_response=final,
            tasks=self.tasks,
            strategy=self.strategy,
            total_time_ms=elapsed,
            agents_used=agents_used,
        )

    async def _execute_sequential(self, brain: Any) -> None:
        """Execute tasks one by one, passing context forward."""
        context = ""
        for task in self.tasks:
            task.status = "running"
            instruction = task.instruction
            if context:
                instruction = f"Previous context:\n{context}\n\nYour task: {instruction}"

            result = await self._run_agent_task(brain, task.agent_name, instruction)
            task.result = result
            task.status = "completed"
            context += f"\n[{task.agent_name}]: {result}"

    async def _execute_parallel(self, brain: Any) -> None:
        """Execute independent tasks in parallel, respecting dependencies."""
        completed_ids: set[str] = set()

        while True:
            # Find tasks ready to run
            ready = [
                t for t in self.tasks
                if t.status == "pending"
                and all(dep in completed_ids for dep in t.depends_on)
            ]

            if not ready:
                break

            # Run all ready tasks in parallel
            async def run_task(task: AgentTask) -> None:
                task.status = "running"
                # Gather dependency results as context
                dep_context = "\n".join(
                    f"[{dt.agent_name}]: {dt.result}"
                    for dt in self.tasks if dt.id in task.depends_on and dt.result
                )
                instruction = task.instruction
                if dep_context:
                    instruction = f"Context from previous steps:\n{dep_context}\n\nYour task: {instruction}"

                task.result = await self._run_agent_task(brain, task.agent_name, instruction)
                task.status = "completed"

            await asyncio.gather(*(run_task(t) for t in ready))
            completed_ids.update(t.id for t in ready)

    async def _execute_hierarchical(self, brain: Any) -> None:
        """Supervisor agent delegates and reviews sub-agent work."""
        context_parts = []
        for task in self.tasks:
            task.status = "running"
            result = await self._run_agent_task(brain, task.agent_name, task.instruction)
            task.result = result
            task.status = "completed"
            context_parts.append(f"[{task.agent_name}]: {result}")

        # Supervisor reviews all results
        review_prompt = (
            "You are the supervisor. Review the work from your team:\n\n"
            + "\n\n".join(context_parts)
            + f"\n\nOriginal task: {self.task}\n"
            "Synthesize the best final answer. Fix any issues."
        )
        supervisor_result = await self._run_agent_task(brain, "companion", review_prompt)

        # Add supervisor review as final task
        self.tasks.append(AgentTask(
            id="supervisor",
            agent_name="companion",
            instruction="Supervisor review",
            status="completed",
            result=supervisor_result,
        ))

    async def _execute_debate(self, brain: Any) -> None:
        """Agents debate/critique each other's responses."""
        if len(self.tasks) < 2:
            await self._execute_sequential(brain)
            return

        # Round 1: Each agent gives initial response
        for task in self.tasks:
            task.status = "running"
            task.result = await self._run_agent_task(brain, task.agent_name, task.instruction)
            task.status = "completed"

        # Round 2+: Each agent critiques and improves
        for round_num in range(1, self.max_rounds):
            all_responses = "\n".join(
                f"[{t.agent_name}]: {t.result}" for t in self.tasks
            )
            for task in self.tasks:
                critique_prompt = (
                    f"Other agents' responses:\n{all_responses}\n\n"
                    f"Original task: {self.task}\n"
                    "Critique the other responses and provide your improved answer."
                )
                task.result = await self._run_agent_task(
                    brain, task.agent_name, critique_prompt,
                )

    async def _run_agent_task(self, brain: Any, agent_name: str, instruction: str) -> str:
        """Run a single agent with an instruction."""
        try:
            result = await brain.process(instruction, session_id=f"crew-{agent_name}")
            return result.response
        except Exception as e:
            logger.warning("Agent '%s' failed in crew: %s", agent_name, e)
            return f"Error: {e}"

    def _synthesize_results(self) -> str:
        """Combine all task results into a final response."""
        completed = [t for t in self.tasks if t.status == "completed" and t.result]
        if not completed:
            return "No agents were able to complete the task."

        if len(completed) == 1:
            return completed[0].result

        # Use the last task's result (usually the synthesis/supervisor)
        return completed[-1].result


# Convenience function for quick crew execution
async def run_crew(
    brain: Any,
    task: str,
    agents: list[str] | None = None,
    strategy: str = "sequential",
) -> CrewResult:
    """Quick way to run a multi-agent crew."""
    crew = Crew(task=task, agents=agents, strategy=strategy)
    return await crew.execute(brain)
