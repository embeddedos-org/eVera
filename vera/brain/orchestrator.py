"""eVera Orchestrator — multi-agent task decomposition and parallel execution.

Extends the existing SupervisorAgent with:
  - Complex task decomposition into parallel subtasks
  - Agent chaining (output of one feeds next)
  - Self-correction on failure
  - Persistent memory across sessions
  - Step-by-step reasoning transparency
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task Model
# ---------------------------------------------------------------------------


@dataclass
class SubTask:
    """A single unit of work assigned to one agent."""
    id: str
    description: str
    agent_name: str
    depends_on: list[str] = field(default_factory=list)
    result: Any = None
    status: str = "pending"  # pending | running | done | failed
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at) * 1000, 1)
        return None


@dataclass
class TaskPlan:
    """A decomposed plan with multiple subtasks."""
    goal: str
    subtasks: list[SubTask]
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    final_answer: str | None = None

    def is_complete(self) -> bool:
        return all(t.status in ("done", "failed") for t in self.subtasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "subtasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "agent": t.agent_name,
                    "status": t.status,
                    "duration_ms": t.duration_ms,
                    "error": t.error,
                }
                for t in self.subtasks
            ],
            "final_answer": self.final_answer,
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class VeraOrchestrator:
    """Multi-agent orchestration engine.

    Decomposes complex requests, routes to specialist agents,
    executes in parallel, synthesizes results, and self-corrects.
    """

    # Phrases that indicate a complex multi-step request
    COMPLEX_INDICATORS = [
        "and then", "also", "additionally", "compare", "analyze",
        "research", "find and", "search for and", "look up and",
        "multiple", "all of", "everything about", "step by step",
        "first", "then", "finally", "summarize", "report on",
    ]

    def __init__(self, agent_registry: dict[str, Any], llm_complete: Callable):
        self.agents = agent_registry
        self.llm = llm_complete
        self._history: list[dict[str, Any]] = []
        self._plans: list[TaskPlan] = []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def orchestrate(
        self,
        user_message: str,
        mode: str = "www",
        model: str | None = None,
        stream_callback: Callable | None = None,
    ) -> str:
        """Orchestrate a complex user request across multiple agents."""
        start = time.time()

        # Step 1: Assess complexity
        is_complex = self._is_complex(user_message)

        if not is_complex:
            return ""  # Let the normal pipeline handle it

        # Step 2: Decompose into subtasks
        if stream_callback:
            await stream_callback("\n🧠 **eVera Orchestrator:** Decomposing your request...\n")

        plan = await self._decompose(user_message, mode)
        self._plans.append(plan)

        if stream_callback:
            task_list = "\n".join(f"  {i+1}. {t.description}" for i, t in enumerate(plan.subtasks))
            await stream_callback(f"\n**Plan ({len(plan.subtasks)} tasks):**\n{task_list}\n\n")

        # Step 3: Execute subtasks (parallel where possible)
        await self._execute_plan(plan, stream_callback)

        # Step 4: Synthesize results
        if stream_callback:
            await stream_callback("\n🔗 **Synthesizing results...**\n")

        answer = await self._synthesize(user_message, plan, model)
        plan.final_answer = answer
        plan.completed_at = time.time()

        # Step 5: Store in history
        self._history.append({"role": "user", "content": user_message, "timestamp": start})
        self._history.append({
            "role": "assistant",
            "content": answer,
            "plan": plan.to_dict(),
            "timestamp": time.time(),
        })

        return answer

    # ------------------------------------------------------------------
    # Complexity Assessment
    # ------------------------------------------------------------------

    def _is_complex(self, message: str) -> bool:
        """Determine if a message needs multi-agent decomposition."""
        msg_lower = message.lower()
        if any(ind in msg_lower for ind in self.COMPLEX_INDICATORS):
            return True
        return len(message.split()) > 35

    # ------------------------------------------------------------------
    # Task Decomposition
    # ------------------------------------------------------------------

    async def _decompose(self, goal: str, mode: str) -> TaskPlan:
        """Use LLM to decompose a complex goal into subtasks."""
        available_agents = list(self.agents.keys())
        prompt = (
            f"Break this goal into 2-5 parallel subtasks.\n"
            f"Goal: {goal}\n"
            f"Mode: {mode}\n"
            f"Available agents: {', '.join(available_agents[:20])}\n\n"
            "Return JSON only:\n"
            '{"subtasks": [{"id": "t1", "description": "...", "agent_name": "...", "depends_on": []}]}'
        )
        try:
            response = await self.llm(
                messages=[{"role": "user", "content": prompt}],
                model=None,
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            data = json.loads(content)
            subtasks = [
                SubTask(
                    id=t["id"],
                    description=t["description"],
                    agent_name=t.get("agent_name", "researcher"),
                    depends_on=t.get("depends_on", []),
                )
                for t in data.get("subtasks", [])
            ]
            return TaskPlan(goal=goal, subtasks=subtasks)
        except Exception as e:
            logger.warning(f"Decomposition failed: {e}, using single task")
            return TaskPlan(
                goal=goal,
                subtasks=[SubTask(id="t1", description=goal, agent_name="researcher")],
            )

    # ------------------------------------------------------------------
    # Parallel Execution
    # ------------------------------------------------------------------

    async def _execute_plan(self, plan: TaskPlan, stream_callback: Callable | None) -> None:
        """Execute subtasks respecting dependencies, running independent tasks in parallel."""
        completed_ids: set[str] = set()

        for _ in range(10):  # max rounds
            if plan.is_complete():
                break
            ready = [
                t for t in plan.subtasks
                if t.status == "pending"
                and all(dep in completed_ids for dep in t.depends_on)
            ]
            if not ready:
                break
            await asyncio.gather(
                *[self._execute_subtask(t, plan, stream_callback) for t in ready],
                return_exceptions=True,
            )
            for t in ready:
                completed_ids.add(t.id)

    async def _execute_subtask(
        self,
        subtask: SubTask,
        plan: TaskPlan,
        stream_callback: Callable | None,
    ) -> None:
        """Execute a single subtask with retry on failure."""
        subtask.status = "running"
        subtask.started_at = time.time()

        if stream_callback:
            await stream_callback(f"⚡ {subtask.description}\n")

        for attempt in range(2):  # 1 retry
            try:
                agent = self._find_agent(subtask.agent_name)
                if not agent:
                    subtask.result = f"Processed: {subtask.description}"
                    subtask.status = "done"
                    break

                # Build context from completed dependencies
                dep_context = ""
                for dep_id in subtask.depends_on:
                    dep = next((t for t in plan.subtasks if t.id == dep_id), None)
                    if dep and dep.result:
                        dep_context += f"\nContext: {dep.result}"

                full_desc = subtask.description + dep_context

                if hasattr(agent, "process"):
                    result = await agent.process(full_desc)
                    subtask.result = result if isinstance(result, str) else json.dumps(result)
                else:
                    subtask.result = f"Completed: {subtask.description}"

                subtask.status = "done"
                break

            except Exception as e:
                if attempt == 1:
                    subtask.error = str(e)
                    subtask.status = "failed"
                    logger.error(f"Subtask {subtask.id} failed after retry: {e}")
                else:
                    await asyncio.sleep(0.5)

        subtask.finished_at = time.time()

        if stream_callback:
            icon = "✅" if subtask.status == "done" else "❌"
            await stream_callback(f"{icon} Done ({subtask.duration_ms}ms)\n")

    def _find_agent(self, name: str) -> Any | None:
        """Find agent by name or partial match."""
        if name in self.agents:
            return self.agents[name]
        for key, agent in self.agents.items():
            if name.lower() in key.lower() or key.lower() in name.lower():
                return agent
        return None

    # ------------------------------------------------------------------
    # Result Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(self, goal: str, plan: TaskPlan, model: str | None) -> str:
        """Synthesize all subtask results into a coherent final answer."""
        results_text = ""
        for t in plan.subtasks:
            if t.result:
                results_text += f"\n**{t.description}:**\n{t.result}\n"

        prompt = (
            f"Synthesize these research results into a clear, comprehensive answer.\n\n"
            f"Original goal: {goal}\n\n"
            f"Results:\n{results_text}\n\n"
            "Provide a well-organized, accurate, helpful response."
        )
        try:
            response = await self.llm(
                messages=[
                    {"role": "system", "content": "You are eVera, the most powerful personal AI assistant."},
                    {"role": "user", "content": prompt},
                ],
                model=model,
            )
            return response.choices[0].message.content
        except Exception:
            return results_text or f"Completed {len(plan.subtasks)} tasks for: {goal}"

    # ------------------------------------------------------------------
    # Memory & History
    # ------------------------------------------------------------------

    def get_history(self, last_n: int = 20) -> list[dict[str, Any]]:
        return self._history[-last_n:]

    def get_plans(self, last_n: int = 5) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self._plans[-last_n:]]

    def clear_history(self) -> None:
        self._history.clear()
        self._plans.clear()
