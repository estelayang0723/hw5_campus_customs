"""Command-line entry point for the Campus Customs agent team."""
from __future__ import annotations

import argparse
import asyncio
from uuid import UUID, uuid4

from backend.agents import TeamDeps, build_team, make_toolset, run_agent_loop
from backend.models import AgentRole, AgentRunRequest, AgentRunResponse


async def run_team(request: AgentRunRequest, *, run_id: UUID | None = None) -> AgentRunResponse:
    run_id = run_id or uuid4()
    toolset = make_toolset()
    team = build_team(toolset)
    deps = TeamDeps(run_id=run_id, agents={**team.specialists, AgentRole.BOSS: team.boss}, ticket_id=request.ticket_id)
    async with toolset:
        prompt = request.prompt
        if request.ticket_id is not None:
            prompt = f"Ticket {request.ticket_id}: {prompt}"
        reply = await run_agent_loop(
            team.boss,
            AgentRole.BOSS,
            prompt,
            deps,
            ticket_id=request.ticket_id,
        )
    return AgentRunResponse(run_id=run_id, role=AgentRole.BOSS, model="gpt-6-luna", response=reply)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Campus Customs' Boss agent.")
    parser.add_argument("prompt", help="Question or task for the agent team.")
    parser.add_argument("--ticket-id", type=int, choices=(101, 102, 103))
    args = parser.parse_args()
    request = AgentRunRequest(prompt=args.prompt, ticket_id=args.ticket_id)
    response = asyncio.run(run_team(request))
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
