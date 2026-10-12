"""Read-only FastMCP tools for the three seeded Campus Customs tickets."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"
mcp = FastMCP("Campus Customs Ticket Assistant")


def _fetch_one(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    """Run a parameterized SELECT against the configured database, in read-only mode."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Campus Customs database not found: {DATABASE_PATH}")
    uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        row = connection.execute(sql, params).fetchone()
        return dict(row) if row is not None else None


def _fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Run a parameterized SELECT against the configured database, in read-only mode."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Campus Customs database not found: {DATABASE_PATH}")
    uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


@mcp.tool()
def resolve_ticket_101_bulldog_tee() -> dict[str, Any]:
    """Return database evidence for open ticket 101: size-S Bulldog tee stock and linked reprint invoice/vendor."""
    ticket = _fetch_one(
        """SELECT id, type, requester, subject, sku, size, qty, invoice_id, status, notes, created_at
           FROM tickets WHERE id = ? AND status = ?""",
        (101, "open"),
    )
    if ticket is None:
        return {"ticket_id": 101, "found_open_ticket": False}
    stock = _fetch_one(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (ticket["sku"], ticket["size"]),
    )
    invoice = _fetch_one(
        """SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description,
                  v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days
           FROM invoices AS i LEFT JOIN vendors AS v ON v.id = i.vendor_id
           WHERE i.id = ?""",
        (ticket["invoice_id"],),
    ) if ticket["invoice_id"] is not None else None
    return {
        "ticket": ticket,
        "matching_inventory": stock,
        "linked_invoice_and_vendor": invoice,
        "note": "These are recorded facts only; no stock, payment, or replenishment action is performed.",
    }


@mcp.tool()
def resolve_ticket_102_rent_notice() -> dict[str, Any]:
    """Return database evidence for open ticket 102: linked lease, current cash snapshot, and recorded payment rows."""
    ticket = _fetch_one(
        """SELECT id, type, requester, subject, lease_id, status, notes, created_at
           FROM tickets WHERE id = ? AND status = ?""",
        (102, "open"),
    )
    if ticket is None:
        return {"ticket_id": 102, "found_open_ticket": False}
    lease = _fetch_one(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (ticket["lease_id"],),
    ) if ticket["lease_id"] is not None else None
    cash_accounts = _fetch_all("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    payments = _fetch_all("SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY id")
    return {
        "ticket": ticket,
        "linked_lease": lease,
        "cash_accounts": cash_accounts,
        "recorded_payments": payments,
        "note": "Payment rows are returned as recorded; the schema does not declare a payment-to-lease foreign key, so reconcile references before treating a row as rent payment.",
    }


@mcp.tool()
def resolve_ticket_103_bulk_hoodie_request() -> dict[str, Any]:
    """Return database evidence for open ticket 103: requested hoodie quantity, size-M stock, and SKU cost/list price."""
    ticket = _fetch_one(
        """SELECT id, type, requester, subject, sku, size, qty, status, notes, created_at
           FROM tickets WHERE id = ? AND status = ?""",
        (103, "open"),
    )
    if ticket is None:
        return {"ticket_id": 103, "found_open_ticket": False}
    stock = _fetch_one(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (ticket["sku"], ticket["size"]),
    )
    pricing = _fetch_one(
        "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
        (ticket["sku"],),
    )
    return {
        "ticket": ticket,
        "matching_inventory": stock,
        "sku_pricing": pricing,
        "note": "The database contains no discount policy or approval fields; no discount or inventory commitment is made.",
    }


@mcp.tool()
def list_open_tickets() -> dict[str, Any]:
    """List the current desk date and all open tickets for triage."""
    desk = _fetch_one("SELECT date_today, notes FROM desk LIMIT 1", ())
    tickets = _fetch_all(
        """SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id,
                  status, notes, created_at
           FROM tickets WHERE lower(status) = ? ORDER BY id""",
        ("open",),
    )
    return {"desk": desk, "open_tickets": tickets}


@mcp.tool()
def lookup_inventory(sku: str, size: str | None = None) -> dict[str, Any]:
    """Look up recorded stock rows for a SKU, optionally narrowed to one size."""
    if size is None:
        rows = _fetch_all(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
            (sku,),
        )
    else:
        rows = _fetch_all(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        )
    return {"sku": sku, "requested_size": size, "inventory_rows": rows}


@mcp.tool()
def lookup_product_pricing(sku: str) -> dict[str, Any]:
    """Return recorded unit cost and list price for one SKU, if present."""
    return {"sku": sku, "pricing": _fetch_one(
        "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
    )}


@mcp.tool()
def get_invoice_context(invoice_id: int) -> dict[str, Any]:
    """Return invoice/vendor details and current cash/payment records for accounting review."""
    invoice = _fetch_one(
        """SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description,
                  v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days
           FROM invoices AS i LEFT JOIN vendors AS v ON v.id = i.vendor_id
           WHERE i.id = ?""",
        (invoice_id,),
    )
    cash_accounts = _fetch_all("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    payments = _fetch_all(
        "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY id"
    )
    return {
        "invoice": invoice,
        "cash_accounts": cash_accounts,
        "recorded_payments": payments,
        "note": "Payment rows are not assumed to reference this invoice; reconcile their kind and ref_id before drawing that conclusion.",
    }


@mcp.tool()
def get_lease_context(lease_id: int) -> dict[str, Any]:
    """Return lease terms, cash snapshots, and payment records for facilities review."""
    lease = _fetch_one(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (lease_id,),
    )
    cash_accounts = _fetch_all("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    payments = _fetch_all(
        "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY id"
    )
    return {
        "lease": lease,
        "cash_accounts": cash_accounts,
        "recorded_payments": payments,
        "note": "The schema has no declared payment-to-lease foreign key; reconcile payment references before treating a row as rent payment.",
    }


@mcp.tool()
def get_customer_order_context(ticket_id: int) -> dict[str, Any]:
    """Return customer-safe order facts for ticket 101 or 103, excluding internal cost/accounting data."""
    if ticket_id not in (101, 103):
        return {"ticket_id": ticket_id, "available": False, "reason": "Only merchandise request tickets 101 and 103 have customer-safe context."}
    ticket = _fetch_one(
        """SELECT id, type, requester, subject, sku, size, qty, status, notes
           FROM tickets WHERE id = ? AND status = ?""",
        (ticket_id, "open"),
    )
    if ticket is None:
        return {"ticket_id": ticket_id, "found_open_ticket": False}
    stock = _fetch_one(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (ticket["sku"], ticket["size"]),
    )
    listed = _fetch_one(
        "SELECT sku, list_price FROM pricing WHERE sku = ?",
        (ticket["sku"],),
    )
    return {
        "ticket": ticket,
        "matching_inventory": stock,
        "customer_list_price": listed,
        "note": "Only customer-relevant list price is returned; internal unit cost, cash balances, invoices, and payments are excluded. No customer commitment is made.",
    }


if __name__ == "__main__":
    mcp.run()
