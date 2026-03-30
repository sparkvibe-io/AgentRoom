"""Builds per-agent system prompts from room state."""

from __future__ import annotations

from agentroom.agents.base import AgentAdapter
from agentroom.protocol.extensions import RoomPhase
from agentroom.protocol.models import RoomState


class RoomPromptBuilder:
    """Assembles a system prompt for each agent based on room context."""

    def build(self, agent: AgentAdapter, room: RoomState, agent_names: list[str]) -> str:
        others = [n for n in agent_names if n != agent.name]
        lines = [
            f'You are {agent.name}, participating in a collaborative room: "{room.config.goal}"',
            f"Your role: {agent.card.role.value}",
            f"Current phase: {room.phase.value}",
            f"Other participants: {', '.join(others)}" if others else "",
            "",
            "Rules:",
            "- Respond in markdown. Be concise and actionable.",
            "- When voting on a proposal, clearly state +1 (agree), 0 (neutral), or -1 (block) with rationale.",
            "- Build on what other agents have said — don't repeat their work.",
            "- If you disagree, explain why with evidence.",
        ]

        if room.phase == RoomPhase.RESEARCHING:
            lines.append("- Focus on gathering information and proposing approaches.")
        elif room.phase == RoomPhase.CONSENSUS:
            lines.append("- Evaluate proposals and vote. Aim for agreement.")
        elif room.phase == RoomPhase.IMPLEMENTING:
            lines.append("- Write clean, working code. Follow best practices.")
        elif room.phase == RoomPhase.REVIEWING:
            lines.append(
                "- Post structured reviews: comment (informational), "
                "suggestion (improvement), or blocking (must fix)."
            )

        return "\n".join(line for line in lines if line is not None)
