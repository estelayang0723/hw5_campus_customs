"""Validated request, response, role, and audit data types."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TicketId = Literal[101, 102, 103]


class AgentRole(str, Enum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class AgentRunRequest(BaseModel):
    """User request accepted by the team runner."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4_000)
    ticket_id: TicketId | None = None


class AgentReply(BaseModel):
    """Evidence-grounded response format shared by the team."""

    summary: str = Field(description="Concise conclusion based only on returned database evidence")
    evidence: list[str] = Field(default_factory=list, description="Relevant database facts and table names")
    unknowns: list[str] = Field(default_factory=list, description="Missing facts or approvals")
    recommendation: str = Field(description="Suggested next step; never claim an action was performed")
    human_approval_needed: bool = Field(
        default=True,
        description="True whenever a customer commitment, money movement, or policy decision is involved",
    )


class AgentRunResponse(BaseModel):
    run_id: UUID
    role: AgentRole
    model: Literal["gpt-6-luna"]
    response: AgentReply


class AuditRecord(BaseModel):
    """Minimal non-sensitive record for one agent graph step."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID
    agent_run_id: UUID
    agent_role: AgentRole
    step: int = Field(ge=0)
    event: Literal["run_started", "graph_step", "run_completed", "run_failed"]
    node_type: str | None = None
    tool_name: str | None = None
    tool_names: list[str] = Field(default_factory=list)
    message: str | None = Field(default=None, max_length=500)
    ticket_id: TicketId | None = None
    usage: dict[str, int] | None = None
    error_type: str | None = None
