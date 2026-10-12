"""Five-role PydanticAI team sharing one read-only MCP toolset."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastmcp.client.transports import StdioTransport
from pydantic import Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset

from backend.audit import append_audit_record
from backend.config import MCP_SERVER, RUN_USAGE_LIMITS, make_model, model_settings
from backend.live_events import publish as publish_live_event
from backend.models import AgentReply, AgentRole, AuditRecord, TicketId

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
ROLE_TOOL_ALLOWLIST = {
    AgentRole.INVENTORY: frozenset({"lookup_inventory"}),
    AgentRole.ACCOUNTING: frozenset({
        "resolve_ticket_101_bulldog_tee",
        "resolve_ticket_102_rent_notice",
        "resolve_ticket_103_bulk_hoodie_request",
        "list_open_tickets",
        "lookup_inventory",
        "lookup_product_pricing",
        "get_invoice_context",
        "get_lease_context",
    }),
    AgentRole.FACILITIES: frozenset({"resolve_ticket_102_rent_notice", "get_lease_context"}),
    AgentRole.CUSTOMER_SERVICE: frozenset({"get_customer_order_context", "lookup_inventory"}),
}
SPECIALIST_ROLES = {
    AgentRole.INVENTORY,
    AgentRole.ACCOUNTING,
    AgentRole.FACILITIES,
    AgentRole.CUSTOMER_SERVICE,
}


@dataclass(slots=True)
class TeamDeps:
    run_id: UUID
    agents: dict[AgentRole, Agent[Any, AgentReply]]
    ticket_id: TicketId | None = None
    delegation_path: tuple[AgentRole, ...] = (AgentRole.BOSS,)


@dataclass(slots=True)
class AgentTeam:
    boss: Agent[TeamDeps, AgentReply]
    specialists: dict[AgentRole, Agent[TeamDeps, AgentReply]]
    toolset: MCPToolset


def make_toolset() -> MCPToolset:
    """Create one shared local stdio MCP connection for the full agent team."""
    return MCPToolset(StdioTransport(command=sys.executable, args=[str(MCP_SERVER)]))


def build_team(toolset: MCPToolset) -> AgentTeam:
    model = make_model()
    settings = model_settings()

    specialists: dict[AgentRole, Agent[TeamDeps, AgentReply]] = {}
    for role in SPECIALIST_ROLES:
        prompt = (PROMPT_DIR / f"{role.value}.md").read_text(encoding="utf-8")
        allowed_tools = ROLE_TOOL_ALLOWLIST[role]
        scoped_toolset = toolset.filtered(
            lambda _ctx, tool_definition, allowed=allowed_tools: tool_definition.name in allowed
        )
        specialists[role] = Agent(
            model,
            name=role.value,
            deps_type=TeamDeps,
            output_type=AgentReply,
            instructions=prompt,
            model_settings=settings,
            toolsets=[scoped_toolset],
            retries=1,
        )

    async def delegate_to_specialist(
        ctx: RunContext[TeamDeps],
        caller_role: AgentRole,
        role: AgentRole,
        task: Annotated[str, Field(min_length=1, max_length=4_000)],
        ticket_id: TicketId | None = None,
    ) -> str:
        """Delegate a focused evidence-gathering task with a strict depth cap."""
        if role == caller_role:
            raise ValueError("An agent cannot delegate to itself.")
        if len(ctx.deps.delegation_path) >= len(AgentRole):
            raise ValueError("Maximum delegation depth reached.")
        specialist_deps = TeamDeps(
            run_id=ctx.deps.run_id,
            agents=ctx.deps.agents,
            ticket_id=ticket_id if ticket_id is not None else ctx.deps.ticket_id,
            delegation_path=(*ctx.deps.delegation_path, role),
        )
        reply = await run_agent_loop(
            ctx.deps.agents[role],
            role,
            task,
            specialist_deps,
            ticket_id=specialist_deps.ticket_id,
            usage=ctx.usage,
        )
        return reply.model_dump_json()

    def attach_delegation_tool(caller_role: AgentRole, specialist: Agent[TeamDeps, AgentReply]) -> None:
        async def consult_specialist(
            ctx: RunContext[TeamDeps],
            role: AgentRole,
            task: Annotated[str, Field(min_length=1, max_length=4_000)],
            ticket_id: TicketId | None = None,
        ) -> str:
            """Ask another available role to gather focused evidence."""
            if not isinstance(role, AgentRole):
                raise ValueError("Choose a valid Campus Customs agent role.")
            return await delegate_to_specialist(ctx, caller_role, role, task, ticket_id)

        consult_specialist.__name__ = "consult_specialist"
        specialist.tool(consult_specialist)

    for caller_role, specialist in specialists.items():
        attach_delegation_tool(caller_role, specialist)

    boss_prompt = (PROMPT_DIR / "boss.md").read_text(encoding="utf-8")
    boss: Agent[TeamDeps, AgentReply] = Agent(
        model,
        name=AgentRole.BOSS.value,
        deps_type=TeamDeps,
        output_type=AgentReply,
        instructions=boss_prompt,
        model_settings=settings,
        toolsets=[toolset],
        retries=1,
    )

    @boss.tool
    async def consult_specialist(
        ctx: RunContext[TeamDeps],
        role: AgentRole,
        task: Annotated[str, Field(min_length=1, max_length=4_000)],
        ticket_id: TicketId | None = None,
    ) -> str:
        """Delegate a focused evidence-gathering task to one specialist agent."""
        if role not in SPECIALIST_ROLES:
            raise ValueError("Boss can delegate only to inventory, accounting, facilities, or customer_service.")
        return await delegate_to_specialist(ctx, AgentRole.BOSS, role, task, ticket_id)

    return AgentTeam(boss=boss, specialists=specialists, toolset=toolset)


async def run_agent_loop(
    agent: Agent[TeamDeps, AgentReply],
    role: AgentRole,
    prompt: str,
    deps: TeamDeps,
    *,
    ticket_id: TicketId | None = None,
    usage: Any = None,
) -> AgentReply:
    """Run and audit each node of the agent graph, without recording message content."""
    step = 0
    agent_run_id = uuid4()
    append_audit_record(AuditRecord(
        run_id=deps.run_id,
        agent_run_id=agent_run_id,
        agent_role=role,
        step=step,
        event="run_started",
        ticket_id=ticket_id,
    ))
    await publish_live_event(deps.run_id, {
        "type": "agent_started",
        "agent_role": role.value,
        "ticket_id": ticket_id,
        "message": f"{role.value.replace('_', ' ').title()} started reviewing the ticket.",
    })
    try:
        async with agent.iter(
            prompt,
            deps=deps,
            usage=usage,
            usage_limits=RUN_USAGE_LIMITS,
        ) as agent_run:
            async for node in agent_run:
                step += 1
                node_type = type(node).__name__
                model_response = getattr(node, "model_response", None)
                tool_names = [
                    str(getattr(part, "tool_name"))
                    for part in getattr(model_response, "parts", ())
                    if getattr(part, "part_kind", None) == "tool-call"
                    and getattr(part, "tool_name", None)
                    and not str(getattr(part, "tool_name")).startswith("__pydantic_ai_")
                    and str(getattr(part, "tool_name")) != "final_result"
                ]
                append_audit_record(AuditRecord(
                    run_id=deps.run_id,
                    agent_run_id=agent_run_id,
                    agent_role=role,
                    step=step,
                    event="graph_step",
                    node_type=node_type,
                    tool_names=tool_names,
                    ticket_id=ticket_id,
                ))
                await publish_live_event(deps.run_id, {
                    "type": "agent_action",
                    "agent_role": role.value,
                    "ticket_id": ticket_id,
                    "node_type": node_type,
                    "tool_names": tool_names,
                    "message": (
                        f"{role.value.replace('_', ' ').title()} called {', '.join(tool_names)}."
                        if tool_names else f"{role.value.replace('_', ' ').title()} is working ({node_type})."
                    ),
                })
            result = agent_run.result
        if result is None:
            raise RuntimeError("Agent run ended without a validated result.")
        run_usage = result.usage
        usage_summary = {
            key: int(getattr(run_usage, key, 0) or 0)
            for key in ("requests", "tool_calls", "input_tokens", "output_tokens")
        }
        append_audit_record(AuditRecord(
            run_id=deps.run_id,
            agent_run_id=agent_run_id,
            agent_role=role,
            step=step + 1,
            event="run_completed",
            ticket_id=ticket_id,
            usage=usage_summary,
            message=result.output.summary[:500],
        ))
        await publish_live_event(deps.run_id, {
            "type": "agent_completed",
            "agent_role": role.value,
            "ticket_id": ticket_id,
            "message": result.output.summary,
            "reply": result.output.model_dump(mode="json"),
            "usage": usage_summary,
        })
        return result.output
    except Exception as exc:
        append_audit_record(AuditRecord(
            run_id=deps.run_id,
            agent_run_id=agent_run_id,
            agent_role=role,
            step=step + 1,
            event="run_failed",
            ticket_id=ticket_id,
            error_type=type(exc).__name__,
        ))
        await publish_live_event(deps.run_id, {
            "type": "agent_failed",
            "agent_role": role.value,
            "ticket_id": ticket_id,
            "message": f"{role.value.replace('_', ' ').title()} stopped with {type(exc).__name__}.",
        })
        raise
