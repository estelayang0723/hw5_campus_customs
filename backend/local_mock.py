"""Deterministic, database-grounded PydanticAI model for token-free local runs."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo

from backend.models import AgentReply
from backend.config import ROOT


_TOOL_BY_TICKET = {
    101: "resolve_ticket_101_bulldog_tee",
    102: "resolve_ticket_102_rent_notice",
    103: "resolve_ticket_103_bulk_hoodie_request",
}


def _find_ticket(messages: list[ModelMessage]) -> int | None:
    # Read prompts and returned tool records only; never infer ticket facts from memory.
    for message in messages:
        for part in getattr(message, "parts", ()):
            content = getattr(part, "content", None)
            if isinstance(content, str):
                match = re.search(r"\b(101|102|103)\b", content)
                if match:
                    return int(match.group(1))
    return None


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(value, list):
        # MCP clients may represent text content as a list of content blocks.
        for block in value:
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if isinstance(text, str):
                parsed = _as_dict(text)
                if parsed is not None:
                    return parsed
    return None


def _evidence_from_tool_returns(messages: list[ModelMessage]) -> list[tuple[str, dict[str, Any]]]:
    evidence: list[tuple[str, dict[str, Any]]] = []
    for message in messages:
        for part in getattr(message, "parts", ()):
            if getattr(part, "part_kind", None) != "tool-return":
                continue
            data = _as_dict(getattr(part, "content", None))
            if data is not None:
                evidence.append((str(getattr(part, "tool_name", "database tool")), data))
    return evidence


def _render_facts(tool_name: str, data: dict[str, Any]) -> list[str]:
    """Turn only returned database fields into compact, customer-safe evidence."""
    facts: list[str] = []
    nested_evidence = data.get("evidence")
    if isinstance(nested_evidence, list):
        facts.extend(str(item) for item in nested_evidence if isinstance(item, str))
    nested_summary = data.get("summary")
    if isinstance(nested_summary, str) and nested_summary:
        facts.append(f"{tool_name}.summary={nested_summary}")
    ticket = data.get("ticket")
    if isinstance(ticket, dict):
        facts.append(
            f"tickets.id={ticket.get('id')} status={ticket.get('status')} "
            f"subject={ticket.get('subject')!r}"
        )
        if ticket.get("sku"):
            facts.append(
                f"tickets.sku={ticket['sku']} size={ticket.get('size')} "
                f"requested_qty={ticket.get('qty')}"
            )
    stock = data.get("matching_inventory")
    if isinstance(stock, dict):
        facts.append(
            f"inventory.sku={stock.get('sku')} size={stock.get('size')} "
            f"qty={stock.get('qty')} location={stock.get('location')}"
        )
    inventory_rows = data.get("inventory_rows")
    if isinstance(inventory_rows, list):
        facts.extend(
            f"inventory.sku={row.get('sku')} size={row.get('size')} "
            f"qty={row.get('qty')} location={row.get('location')}"
            for row in inventory_rows if isinstance(row, dict)
        )
    lease = data.get("linked_lease") or data.get("lease")
    if isinstance(lease, dict):
        facts.append(
            f"leases.id={lease.get('id')} monthly_rent={lease.get('monthly_rent')} "
            f"next_due={lease.get('next_due')} landlord={lease.get('landlord')}"
        )
    invoice = data.get("linked_invoice_and_vendor", data.get("invoice"))
    if isinstance(invoice, dict):
        facts.append(
            f"invoices.id={invoice.get('id')} amount={invoice.get('amount')} "
            f"due_date={invoice.get('due_date')} status={invoice.get('status')}"
        )
    pricing = data.get("customer_list_price") or data.get("sku_pricing") or data.get("pricing")
    if isinstance(pricing, dict):
        # Never surface internal unit_cost, even when a tool legitimately returns it.
        safe_pricing = {k: v for k, v in pricing.items() if k != "unit_cost"}
        if safe_pricing:
            facts.append("pricing=" + json.dumps(safe_pricing, ensure_ascii=False, sort_keys=True))
    desk = data.get("desk")
    if isinstance(desk, dict):
        facts.append(f"desk.date_today={desk.get('date_today')}")
    accounts = data.get("cash_accounts")
    if isinstance(accounts, list):
        facts.extend(
            f"cash_accounts.name={row.get('name')} balance={row.get('balance')} date={row.get('date')}"
            for row in accounts if isinstance(row, dict)
        )
    payments = data.get("recorded_payments")
    if isinstance(payments, list):
        facts.append(f"payments.record_count={len(payments)}")
    open_tickets = data.get("open_tickets")
    if isinstance(open_tickets, list):
        facts.append("tickets.open_ids=" + ",".join(str(row.get("id")) for row in open_tickets if isinstance(row, dict)))
    if not facts:
        facts.append(f"{tool_name} returned no matching record in the database.")
    return facts


def _reply_args(messages: list[ModelMessage]) -> dict[str, Any]:
    gathered = _evidence_from_tool_returns(messages)
    facts = [fact for tool, data in gathered for fact in _render_facts(tool, data)]
    facts = list(dict.fromkeys(facts))
    ticket_id = _find_ticket(messages)
    if facts:
        summary = "Local mock reviewed read-only database results; see the cited table fields below."
        recommendation = "A human should verify the cited records and approve any customer commitment, payment, or policy decision."
        unknowns = ["The database does not establish authorization for external actions or commitments."]
    else:
        summary = "The local mock found no database tool result to support a factual conclusion."
        recommendation = "Call the relevant read-only database tool before responding."
        unknowns = ["No matching database evidence was returned."]
    if ticket_id is not None:
        facts.insert(0, f"Ticket context: {ticket_id} (ticket number detected from the current run prompt/tool history).")
    return AgentReply(
        summary=summary,
        evidence=facts,
        unknowns=unknowns,
        recommendation=recommendation,
        human_approval_needed=True,
    ).model_dump(mode="json")


def local_mock_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Call one relevant MCP tool, then return a schema-valid response from its result."""
    available = {tool.name for tool in info.function_tools}
    returns = _evidence_from_tool_returns(messages)
    role_text = str(info.instructions or "").lower()
    ticket_id = _find_ticket(messages)
    if ticket_id is not None and "consult_specialist" in available and role_text.startswith("you are the boss agent"):
        expected_roles = {
            101: ["inventory", "accounting"],
            102: ["facilities", "accounting"],
            103: ["inventory", "accounting", "customer_service"],
        }[ticket_id]
        completed_roles: set[str] = set()
        for message in messages:
            for part in getattr(message, "parts", ()):
                if getattr(part, "part_kind", None) != "tool-call" or getattr(part, "tool_name", None) != "consult_specialist":
                    continue
                args: Any = getattr(part, "args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                if isinstance(args, dict) and isinstance(args.get("role"), str):
                    completed_roles.add(args["role"])
        next_role = next((role for role in expected_roles if role not in completed_roles), None)
        if next_role:
            return ModelResponse(parts=[ToolCallPart("consult_specialist", {
                "role": next_role,
                "task": f"Review database evidence for ticket {ticket_id} from the {next_role.replace('_', ' ')} perspective.",
                "ticket_id": ticket_id,
            })])
    if not returns:
        # Customer Service remains on its safe surface; Inventory receives only its
        # stock lookup. Other roles use the most specific ticket tool exposed to them.
        if (
            ticket_id in (101, 103)
            and "get_customer_order_context" in available
            and role_text.startswith("you are the customer service agent")
        ):
            return ModelResponse(parts=[ToolCallPart("get_customer_order_context", {"ticket_id": ticket_id})])
        if (
            ticket_id is not None
            and "lookup_inventory" in available
            and role_text.startswith("you are the inventory agent")
        ):
            database_uri = (ROOT / "data" / "campus_customs_new.db").as_uri() + "?mode=ro"
            with sqlite3.connect(database_uri, uri=True) as connection:
                connection.execute("PRAGMA query_only = ON")
                row = connection.execute("SELECT sku, size FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row:
                return ModelResponse(parts=[ToolCallPart("lookup_inventory", {"sku": row[0], "size": row[1]})])
        if ticket_id in _TOOL_BY_TICKET and _TOOL_BY_TICKET[ticket_id] in available:
            return ModelResponse(parts=[ToolCallPart(_TOOL_BY_TICKET[ticket_id], {})])
        if "list_open_tickets" in available:
            return ModelResponse(parts=[ToolCallPart("list_open_tickets", {})])
        # A specialist without a ticket-specific context gets a safe inventory probe only
        # when the supplied prompt includes a SKU; otherwise it must return unknowns.
    if info.output_tools:
        output_tool = info.output_tools[0]
        return ModelResponse(parts=[ToolCallPart(output_tool.name, _reply_args(messages))])
    return ModelResponse(parts=[])
