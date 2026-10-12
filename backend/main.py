"""FastAPI routes for the local Campus Customs dashboard and approval workflow."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import AsyncIterator, Iterator, Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Path as PathParam, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.config import AUDIT_PATH, ROOT
from backend.live_events import publish as publish_live_event, subscribe, unsubscribe
from backend.models import AgentRunRequest
from backend.runner import run_team

DATABASE_PATH = ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DATABASE_PATH = ROOT / "data" / "campus_customs.db"
APPROVAL_TOKEN_ENV = "CAMPUS_CUSTOMS_APPROVAL_TOKEN"
DB_WRITE_LOCK = threading.Lock()
VALID_TICKET_IDS = {101, 102, 103}

app = FastAPI(
    title="Campus Customs Dashboard API",
    version="1.0.0",
    description="Ticket triage, local PydanticAI runs, dashboard events, and explicitly confirmed cash approvals.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Approval-Token"],
)


@contextmanager
def database(read_only: bool = True) -> Iterator[sqlite3.Connection]:
    """Open the working database, read-only unless a route explicitly mutates it."""
    if not DATABASE_PATH.is_file():
        raise HTTPException(status_code=500, detail="Campus Customs database is missing.")
    if read_only:
        connection = sqlite3.connect(f"{DATABASE_PATH.as_uri()}?mode=ro", uri=True, timeout=10)
    else:
        connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


class TicketRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(
        default="Review the ticket, gather relevant database evidence, and recommend a safe next step.",
        min_length=1,
        max_length=4_000,
    )


class ApprovalRequest(BaseModel):
    """An explicit human approval to record and debit one cash outflow."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["payment", "purchase"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    ref_id: int | None = Field(default=None, ge=1)
    account: str = Field(default="checking", min_length=1, max_length=40)
    approved_by: str = Field(min_length=1, max_length=120)
    confirm: Literal[True]

    @field_validator("approved_by", "account")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Must contain non-whitespace characters.")
        return value


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


def _check_optional_approval_token(provided_token: str | None) -> None:
    """If configured, require a local admin token for cash and reset operations."""
    expected = os.getenv(APPROVAL_TOKEN_ENV)
    if expected and (not provided_token or not hmac.compare_digest(provided_token, expected)):
        raise HTTPException(status_code=401, detail="A valid approval token is required.")


def _require_ticket(ticket_id: int) -> None:
    if ticket_id not in VALID_TICKET_IDS:
        raise HTTPException(status_code=404, detail="Unknown ticket id. Expected 101, 102, or 103.")
    with database() as connection:
        exists = connection.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Ticket was not found.")


def _mark_ticket_resolved(ticket_id: int) -> None:
    """Close the ticket only after the agent run returned a validated result."""
    with DB_WRITE_LOCK:
        with database(read_only=False) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE tickets SET status = ? WHERE id = ?", ("resolved", ticket_id))
            connection.commit()


@app.get("/tickets")
def list_tickets() -> dict[str, object]:
    """Return the three seeded tickets, including their current workflow status."""
    with database() as connection:
        rows = connection.execute(
            """SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id,
                      status, notes, created_at
               FROM tickets WHERE id IN (101, 102, 103) ORDER BY id"""
        ).fetchall()
    return {"tickets": [dict(row) for row in rows]}


@app.post("/tickets/{ticket_id}/run")
async def run_ticket_agent(
    ticket_id: int = PathParam(ge=1),
    request: TicketRunRequest | None = None,
) -> dict[str, object]:
    """Run Boss and its relevant agent workflow for one of the three seeded tickets."""
    _require_ticket(ticket_id)
    prompt = request.prompt if request else "Review the ticket, gather relevant database evidence, and recommend a safe next step."
    try:
        result = await run_team(AgentRunRequest(prompt=prompt, ticket_id=ticket_id))
        _mark_ticket_resolved(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent run failed ({type(exc).__name__}).") from exc
    response = result.model_dump(mode="json")
    response["ticket_status"] = "resolved"
    return response


@app.post("/tickets/{ticket_id}/run/stream")
async def stream_ticket_agent(
    ticket_id: int = PathParam(ge=1),
    request: TicketRunRequest | None = None,
) -> StreamingResponse:
    """Stream live agent actions and final structured dialogue for one ticket."""
    _require_ticket(ticket_id)
    prompt = request.prompt if request else "Review the ticket, gather relevant database evidence, and recommend a safe next step."
    run_id = uuid4()
    queue = subscribe(run_id)

    async def execute_run() -> None:
        try:
            result = await run_team(
                AgentRunRequest(prompt=prompt, ticket_id=ticket_id),
                run_id=run_id,
            )
            _mark_ticket_resolved(ticket_id)
            await publish_live_event(run_id, {
                "type": "ticket_resolved",
                "ticket_id": ticket_id,
                "status": "resolved",
                "message": f"Ticket {ticket_id} was marked resolved after the agent team completed.",
                "reply": result.response.model_dump(mode="json"),
            })
        except Exception as exc:
            await publish_live_event(run_id, {
                "type": "run_failed",
                "ticket_id": ticket_id,
                "message": f"Agent run failed ({type(exc).__name__}).",
            })
        finally:
            await publish_live_event(run_id, {"type": "stream_done", "ticket_id": ticket_id})

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(execute_run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                if event.get("type") == "stream_done":
                    break
            await task
        finally:
            unsubscribe(run_id, queue)
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/events")
def recent_agent_events(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, object]:
    """Return the newest audit events first for dashboard polling."""
    if not AUDIT_PATH.exists():
        return {"events": [], "count": 0}
    try:
        records = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="The agent event log is unavailable or invalid.") from exc
    if not isinstance(records, list):
        raise HTTPException(status_code=500, detail="The agent event log must be a JSON array.")
    latest = list(reversed(records[-limit:]))
    return {"events": latest, "count": len(latest)}


@app.post("/approvals")
def approve_cash_outflow(
    request: ApprovalRequest,
    x_approval_token: str | None = Header(default=None),
) -> dict[str, object]:
    """Record a human-confirmed payment/purchase and debit the selected cash account."""
    _check_optional_approval_token(x_approval_token)
    amount = float(request.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive.")
    now = datetime.now(UTC)
    with DB_WRITE_LOCK:
        try:
            with database(read_only=False) as connection:
                connection.execute("BEGIN IMMEDIATE")
                account = connection.execute(
                    "SELECT name, balance, date FROM cash_accounts WHERE name = ?",
                    (request.account,),
                ).fetchone()
                if account is None:
                    raise HTTPException(status_code=404, detail="Cash account was not found.")
                balance = float(account["balance"])
                if amount > balance:
                    raise HTTPException(status_code=409, detail="Insufficient recorded cash balance.")
                cursor = connection.execute(
                    """INSERT INTO payments(kind, ref_id, amount, account, paid_at, approved_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (request.kind, request.ref_id, amount, request.account, now.isoformat(timespec="seconds"), request.approved_by),
                )
                new_balance = round(balance - amount, 2)
                connection.execute(
                    "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                    (new_balance, now.date().isoformat(), request.account),
                )
                connection.commit()
        except HTTPException:
            raise
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="Could not record the approved cash outflow.") from exc
    return {
        "approved": True,
        "payment_id": cursor.lastrowid,
        "kind": request.kind,
        "ref_id": request.ref_id,
        "amount": amount,
        "account": request.account,
        "approved_by": request.approved_by,
        "balance": new_balance,
        "balance_date": now.date().isoformat(),
    }


@app.get("/cash/checking")
def checking_balance() -> dict[str, object]:
    """Return the current recorded checking balance and its snapshot date."""
    with database() as connection:
        row = connection.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?",
            ("checking",),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Checking account was not found.")
    return dict(row)


@app.post("/reset")
def reset_database(
    request: ResetRequest,
    x_approval_token: str | None = Header(default=None),
) -> dict[str, object]:
    """Restore every working database table to the supplied original SQLite file."""
    _check_optional_approval_token(x_approval_token)
    if not ORIGINAL_DATABASE_PATH.is_file():
        raise HTTPException(status_code=500, detail="The original Campus Customs database is missing.")
    if ORIGINAL_DATABASE_PATH.resolve() == DATABASE_PATH.resolve():
        raise HTTPException(status_code=500, detail="Original and working database paths must differ.")
    with DB_WRITE_LOCK:
        try:
            with closing(sqlite3.connect(f"{ORIGINAL_DATABASE_PATH.as_uri()}?mode=ro", uri=True, timeout=10)) as source:
                with closing(sqlite3.connect(DATABASE_PATH, timeout=10)) as destination:
                    source.backup(destination)
                    check = destination.execute("PRAGMA quick_check").fetchone()[0]
                    if check != "ok":
                        raise sqlite3.DatabaseError("Original database failed quick_check.")
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="Could not restore the original database.") from exc
    return {"reset": True, "database": str(DATABASE_PATH.relative_to(ROOT)), "source": str(ORIGINAL_DATABASE_PATH.relative_to(ROOT))}
