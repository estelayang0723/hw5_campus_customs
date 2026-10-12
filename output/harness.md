# Campus Customs Database Harness — Problem 2

## Purpose

This reference documents every table and field in `data/campus_customs_new.db` for the Campus Customs agents. The working copy was made from the supplied `data/campus_customs.db`. Field types and key constraints below are taken from the SQLite schema. `NOT NULL` means a value is required; `NULL` means it may be absent. Primary-key components are marked **PK**; declared foreign keys are marked **FK**.

## Tables and fields

### `cash_accounts`

Tracks available cash by account. Agents use it to assess whether a proposed payment is financially feasible, while checking the snapshot date and recorded payment history. A balance alone does not authorize a payment.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `name` | TEXT | **PK** | Account identifier, such as `checking`; links payment records to the account. |
| `balance` | REAL | NOT NULL | Recorded account balance. |
| `date` | TEXT | NOT NULL | Date the balance applies to; needed to judge freshness. |

### `desk`

Provides the shop's operating date and optional desk context. Agents should use its date when interpreting relative deadlines such as “in two days.”

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `date_today` | TEXT | NOT NULL | Current business date represented by this database snapshot. |
| `notes` | TEXT | NULL | Optional operating notes that may add context. |

### `inventory`

Shows stock by SKU and size. Agents use it to check whether customer orders or bulk requests can be fulfilled and where stock is stored. The primary key is the combination of SKU and size.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `sku` | TEXT | **PK (composite)**, NOT NULL | Product identifier; together with `size` identifies a stock row. |
| `name` | TEXT | NOT NULL | Human-readable product name. |
| `size` | TEXT | **PK (composite)**, NOT NULL | Product size; together with `sku` identifies a stock row. |
| `qty` | INTEGER | NOT NULL | Quantity currently recorded for this SKU and size. |
| `location` | TEXT | NOT NULL | Stock location for fulfillment. |

### `invoices`

Tracks vendor bills, due dates, and payment status. Agents use it to prioritize obligations and connect a ticket or payment to the bill. `vendor_id` references `vendors.id`.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `id` | INTEGER | **PK** | Invoice identifier. |
| `vendor_id` | INTEGER | **FK** → `vendors.id`, NOT NULL | Vendor that issued the invoice. |
| `amount` | REAL | NOT NULL | Amount billed. |
| `due_date` | TEXT | NOT NULL | Invoice due date. |
| `status` | TEXT | NOT NULL | Recorded invoice state, such as open or paid. |
| `description` | TEXT | NULL | Optional description of the billed goods or service. |

### `leases`

Stores rental obligations and due dates. Agents use it to verify rent notices and determine the contractual amount and deadline. Tickets may refer to a lease through `lease_id`.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `id` | INTEGER | **PK** | Lease identifier referenced by rent-related tickets. |
| `space_name` | TEXT | NOT NULL | Name or description of the rented space. |
| `landlord` | TEXT | NOT NULL | Landlord or property manager. |
| `monthly_rent` | REAL | NOT NULL | Recorded monthly rent amount. |
| `next_due` | TEXT | NOT NULL | Next rent due date. |
| `notes` | TEXT | NULL | Optional lease details. |

### `payments`

Records payments that have been made, including their references and approvers. Agents use it to avoid duplicate payment recommendations and to verify payment history. It is an audit record, not an instruction to pay.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `id` | INTEGER | **PK** | Payment record identifier. |
| `kind` | TEXT | NOT NULL | Payment category or referenced obligation type. |
| `ref_id` | INTEGER | NULL | Related record identifier, when supplied. |
| `amount` | REAL | NOT NULL | Amount recorded as paid. |
| `account` | TEXT | NOT NULL | Account used for payment; corresponds to `cash_accounts.name` by convention (no declared FK). |
| `paid_at` | TEXT | NOT NULL | Payment timestamp or date. |
| `approved_by` | TEXT | NOT NULL | Recorded approver. |

### `pricing`

Stores unit cost and list price by SKU. Agents use it to estimate margins and evaluate discount requests; it does not encode discount policy or approval authority.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `sku` | TEXT | **PK** | Product identifier used to look up pricing. |
| `unit_cost` | REAL | NOT NULL | Recorded cost per unit. |
| `list_price` | REAL | NOT NULL | Current recorded list price per unit. |

### `tickets`

Queues customer and business requests for agent review. This is the primary work list; agents use the type, status, details, linked records, and creation time to triage each request. `lease_id` references `leases.id`; `invoice_id` references `invoices.id`.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `id` | INTEGER | **PK** | Ticket identifier. |
| `type` | TEXT | NOT NULL | Request category, such as customer order, rent notice, or price override. |
| `requester` | TEXT | NOT NULL | Person or organization making the request. |
| `subject` | TEXT | NOT NULL | Short ticket title. |
| `sku` | TEXT | NULL | Product identifier when the ticket concerns merchandise. |
| `size` | TEXT | NULL | Product size when applicable. |
| `qty` | INTEGER | NULL | Requested quantity when applicable. |
| `lease_id` | INTEGER | **FK** → `leases.id`, NULL | Related lease for rent or premises requests. |
| `invoice_id` | INTEGER | **FK** → `invoices.id`, NULL | Related invoice, if applicable. |
| `status` | TEXT | NOT NULL | Workflow state; agents use it to find unresolved work. |
| `notes` | TEXT | NULL | Request details or supporting context. |
| `created_at` | TEXT | NOT NULL | Ticket creation timestamp, including timezone where recorded. |

### `vendors`

Lists suppliers and service providers, including specialties and lead times. Agents use it to identify a suitable supplier and estimate replenishment timing; the database does not itself confirm an order has been placed.

| Field | SQLite type | Constraint | Description |
| --- | --- | --- | --- |
| `id` | INTEGER | **PK** | Vendor identifier referenced by invoices. |
| `name` | TEXT | NOT NULL | Vendor name. |
| `specialty` | TEXT | NOT NULL | Goods or services the vendor provides. |
| `lead_days` | INTEGER | NOT NULL | Recorded typical lead time in days. |

## Open-ticket review

The database snapshot's `desk.date_today` is `2026-08-31`. It contains three tickets with status `open`:

| Ticket | Request | Related facts in the database | Agent relevance |
| --- | --- | --- | --- |
| 101 | Tauhid Zaman requests one size-S Bulldog tee (`CC-TEE-WHITE`). | Inventory shows quantity 0 in size S. Linked invoice 501 is open for $840, due 2026-08-28, with description “Rush reprint CC-TEE-WHITE S.” Vendor 1 is Bulldog Print Co, apparel reprint, 5-day lead time. | Cannot fulfill from recorded size-S stock. The invoice is overdue relative to the desk date; check invoice/payment state and coordinate replenishment before promising availability. |
| 102 | Elm City Properties sends a rent notice saying shop rent is due in two days. | Lease 1 is for the Chapel Street shop, monthly rent $2,400, next due 2026-09-02. No payment records are present. | The notice's relative timing agrees with the desk date and lease due date. Verify payment authorization and cash status before action. |
| 103 | Yale AI Club requests a bulk discount on 20 medium navy hoodies (`CC-HOOD-NAVY`). | Inventory shows 8 size-M units. Pricing lists unit cost $22 and list price $58. | Recorded stock is 12 units short. The list price and cost support basic margin calculations, but no discount policy or approval is stored; clarify availability and approval before committing. |

## Data handling notes

- The schema declares foreign keys from `invoices.vendor_id` to `vendors.id`, and from `tickets.lease_id` / `tickets.invoice_id` to `leases.id` / `invoices.id`.
- `payments` is empty in this snapshot; absence of a payment row is not proof that an obligation has been approved or is payable.
- The current `cash_accounts` snapshot has a checking balance of $3,400 dated `2026-08-31`.
- Use read-only analysis for triage. Do not make payments, promise inventory, approve discounts, or alter operational data without the required human authorization.


## Problem 3 — MCP server tools

The read-only FastMCP server is implemented in `mcp_server/server.py` and connects to `data/campus_customs_new.db`. It uses only rows present in that database and does not change operational records.

| MCP tool | Tables read | Open ticket it helps unlock | Why this tool is right for the ticket |
| --- | --- | --- | --- |
| `resolve_ticket_101_bulldog_tee` | `tickets`, `inventory`, `invoices`, `vendors` | 101 | It combines the ticket's exact SKU and size with current stock and the linked reprint invoice/vendor so the agent can assess fulfillment and replenishment evidence. |
| `resolve_ticket_102_rent_notice` | `tickets`, `leases`, `cash_accounts`, `payments` | 102 | It returns the rent notice with its linked lease deadline and amount plus the available cash snapshot and payment records for human reconciliation. |
| `resolve_ticket_103_bulk_hoodie_request` | `tickets`, `inventory`, `pricing` | 103 | It compares the requested size and quantity with matching stock and SKU cost/list price, the database evidence needed to evaluate the bulk request without inventing a discount rule. |


## Problem 5 — Campus Customs agent team

### Agents

All five PydanticAI agents connect to the same local, read-only MCP server, with role-filtered specialist tool access, and use the single configured model `gpt-6-luna` through Portkey. Boss and every specialist expose the internal PydanticAI `consult_specialist` orchestration tool to delegate to another role; it is separate from the MCP database tools.

| Agent | Prompt file | Role |
| --- | --- | --- |
| Boss | `backend/prompts/boss.md` | Triages open tickets, delegates to specialists, and combines evidence into a structured recommendation. |
| Inventory | `backend/prompts/inventory.md` | Verifies SKU/size stock and fulfillment evidence without changing stock or promising replenishment. |
| Accounting | `backend/prompts/accounting.md` | Reviews invoices, vendor details, cash snapshots, and payment records without approving or making payments. |
| Facilities | `backend/prompts/facilities.md` | Verifies lease, rent notice, due date, cash snapshot, and payment context. |
| Customer Service | `backend/prompts/customer_service.md` | Prepares evidence-based customer guidance without promising stock, price, delivery, or discounts. |

### MCP tools and source tables

All five agents connect to the same MCP server; Boss has all tools, and specialists receive role-filtered tool surfaces. Every role can delegate to any other role through `consult_specialist`; delegation is bounded by a five-agent depth cap and the shared workflow usage limits. The database tools provide no write operations.

| MCP tool | Tables read | Available roles | Purpose |
| --- | --- | --- |
| `resolve_ticket_101_bulldog_tee` | `tickets`, `inventory`, `invoices`, `vendors` | Boss, Accounting | Ticket 101 tee availability and linked reprint evidence. |
| `resolve_ticket_102_rent_notice` | `tickets`, `leases`, `cash_accounts`, `payments` | Boss, Accounting, Facilities | Ticket 102 rent notice, lease, cash snapshot, and recorded payments. |
| `resolve_ticket_103_bulk_hoodie_request` | `tickets`, `inventory`, `pricing` | Boss, Accounting | Ticket 103 hoodie request, matching stock, and SKU price/cost. |
| `list_open_tickets` | `desk`, `tickets` | Boss, Accounting | Current desk date and open-ticket queue. |
| `lookup_inventory` | `inventory` | Boss, Inventory, Accounting, Customer Service | Current stock rows by SKU and optional size. |
| `lookup_product_pricing` | `pricing` | Boss, Accounting | Stored unit cost and list price by SKU. |
| `get_invoice_context` | `invoices`, `vendors`, `cash_accounts`, `payments` | Boss, Accounting | Invoice/vendor detail and account/payment records for accounting review. |
| `get_lease_context` | `leases`, `cash_accounts`, `payments` | Boss, Accounting, Facilities | Lease details and account/payment records for facilities review. |
| `get_customer_order_context` | `tickets`, `inventory`, `pricing` (list_price only) | Boss, Customer Service | Safe merchandise ticket context with on-hand stock and customer list price only. |

### Safety and usage limits

- **Customer guardrails:** Use only database evidence; do not expose another customer's data or internal unit costs/account balances. Customer Service is technically filtered to customer-safe order context and inventory, excluding invoice, payment, and cash tools. No agent may send messages or promise stock, delivery dates, substitutions, or discounts.
- **Money guardrails:** MCP tools are read-only; never authorize or initiate payments, refunds, transfers, discounts, or record changes. Treat payment rows as unlinked to invoices/leases unless a human reconciles their references; escalate money and policy decisions for explicit approval.
- **Loop/token guardrails:** Inputs are capped at 4,000 characters; each shared workflow is limited to 10 model requests, 12 successful tool calls, 8,000 input tokens, 4,000 output tokens, and 12,000 total tokens. All delegations share the same usage counter and stop at the five-agent depth limit. Each graph step appends its tool names to `output/audit_trail.json`; completed agent summaries are recorded without storing prompts or full replies.
- **Local mock mode:** `CAMPUS_CUSTOMS_LOCAL_MOCK` defaults to enabled. PydanticAI's local `FunctionModel` selects an available MCP tool, reads its live result from `data/campus_customs_new.db`, and formats a validated response without network calls or token use. Set `CAMPUS_CUSTOMS_LOCAL_MOCK=0` plus `PORTKEY_API_KEY` to run the preserved `gpt-6-luna` Portkey configuration.

## Problem 7 — FastAPI backend routes

| Method and URL | What it does |
| --- | --- |
| `GET /tickets` | Returns tickets 101, 102, and 103 with their current status and summary fields. |
| `POST /tickets/{ticket_id}/run/stream` | Runs the selected ticket's team and streams agent actions/dialogue as server-sent events, then marks it resolved on success. |
| `POST /tickets/{ticket_id}/run` | Runs the Boss PydanticAI workflow for the specified seeded ticket and returns its structured result. |
| `GET /events?limit=50` | Returns recent append-only agent events newest first, including agent role, ticket, graph node, called tool/delegation names, usage, and the concise completion summary. |
| `POST /approvals` | Requires `confirm: true` and `approved_by`, then records a payment or purchase and atomically debits the selected cash account. |
| `GET /cash/checking` | Returns the recorded checking balance and snapshot date. |
| `POST /reset` | Requires `confirm: true` and restores `campus_customs_new.db` from original `campus_customs.db`. |

Cash-changing routes do not change invoice state or inventory; they require an explicit approval body and can additionally require `X-Approval-Token` when `CAMPUS_CUSTOMS_APPROVAL_TOKEN` is configured. Reset restores database tables but preserves the separate audit log.

## Problem 8 — Dashboard

The dashboard is a React + TypeScript application built with Vite in `frontend/`. Start the FastAPI app at `http://localhost:8000`, then run `cd frontend && npm --cache ../.npm-cache install && npm run dev`; Vite serves it at `http://localhost:5173`. FastAPI CORS allows this frontend origin. The dashboard lists all three tickets and statuses, lets a user select and run one ticket, streams agent actions and validated replies from `POST /tickets/{ticket_id}/run/stream`, displays each completed agent's summary and recent audit events, and refreshes the checking balance from `GET /cash/checking`. Cash approvals require an explicit human-confirmation dialog and use `POST /approvals`; a run never submits an approval automatically. Layout, visual choices, responsive behavior, and accessibility are described in `output/design.md`.

## Problem 9 — Actual ticket runs and cash reconciliation

The working database was reset from `data/campus_customs.db` before the corrected three-ticket local-mock PydanticAI run. The starting checking balance was **$3,400.00** dated `2026-08-31`. Tickets 101, 102, and 103 each completed with backend workflow status `resolved`; their final run IDs and per-agent graph events, tool names, and concise completion summaries were appended to `output/audit_trail.json` and outcomes are recorded in `output/resolved_tickets.json`.

| Ticket | Agent contributions and tools recorded | Evidence-grounded outcome | Cash change | Human approval |
| --- | --- | --- | ---: | --- |
| 101 | Boss (`consult_specialist`), Inventory (`lookup_inventory`), Accounting (`resolve_ticket_101_bulldog_tee`) | 0 size-S tees; linked invoice 501 is $840, open and overdue; reprint vendor lead time is 5 days. Customer fulfillment still needs human/vendor follow-up. | $0.00 | None recorded; no stock commitment or invoice payment submitted. |
| 102 | Boss (`consult_specialist`), Facilities and Accounting (`resolve_ticket_102_rent_notice`) | Lease 1 records $2,400 rent due 2026-09-02; checking snapshot is $3,400; no payment row exists. | $0.00 | No rent payment approval recorded. |
| 103 | Boss (`consult_specialist`), Inventory (`lookup_inventory`), Accounting (`resolve_ticket_103_bulk_hoodie_request`), Customer Service (`get_customer_order_context`) | 8 of 20 requested size-M hoodies are in stock; list price is $58; no discount rule is stored. | $0.00 | No discount or purchase approval recorded. |

Ending checking remains **$3,400.00**, matching `cash_accounts.balance`, and `payments` remains empty. The agent workflow status is resolved for all three tickets, while business fulfillment/payment/discount decisions requiring human approval remain outstanding. See the Cash tab in `output/desk_tickets.html` and the ticket board in `output/resolved_board.html` for the same per-ticket cash reconciliation.

## Safety and data integrity summary

- All nine database tables and their fields are documented above; ticket, invoice, lease, inventory, pricing, vendor, payment, and dated cash facts must come from the working database.
- MCP agent tools are read-only. The Boss delegates to only relevant specialists; Customer Service is limited to customer-safe order and inventory context and does not receive internal cost, invoice, payment, or account data.
- Agents do not send messages, promise inventory or delivery, decide discounts, or initiate money movement. Any cash-changing operation requires `confirm: true`, an approver name, sufficient balance, and an optional configured approval token.
- Local mock mode uses the real PydanticAI graph and database-backed MCP results without Portkey/network calls. `gpt-6-luna` Portkey configuration remains available only when explicitly opting into remote mode. Workflow limits and per-step append-only audit behavior are listed in Problem 5 above.
- `/reset` restores the original database and preserves the append-only audit trail; Problem 9 run IDs remain in `output/audit_trail.json` after reset operations.
