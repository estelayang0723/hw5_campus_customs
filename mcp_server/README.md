# Campus Customs MCP Server

## Purpose

This read-only FastMCP server exposes tools for triaging the Campus Customs tickets and retrieving inventory, accounting, lease, and pricing evidence. The five PydanticAI roles in `backend/` connect to this server over stdio through one shared MCP server connection; each specialist receives a role-filtered tool surface, while Boss can access the complete read-only tool list.

## Database

The server connects to `../data/campus_customs_new.db`, resolved relative to `server.py`. SQLite connections use URI read-only mode and enable `query_only`. No tool modifies a ticket, inventory, price, invoice, lease, account, or payment.

## Tools

| Tool | Tables read | What it provides |
| --- | --- | --- |
| `resolve_ticket_101_bulldog_tee` | `tickets`, `inventory`, `invoices`, `vendors` | Ticket 101, matching size-S tee stock, and the linked reprint invoice and vendor. |
| `resolve_ticket_102_rent_notice` | `tickets`, `leases`, `cash_accounts`, `payments` | Ticket 102, linked lease terms, cash snapshots, and recorded payment rows. |
| `resolve_ticket_103_bulk_hoodie_request` | `tickets`, `inventory`, `pricing` | Ticket 103, matching medium hoodie stock, and the SKU cost/list price. |
| `list_open_tickets` | `desk`, `tickets` | Business date and all currently open tickets. |
| `lookup_inventory` | `inventory` | Stock rows for a SKU, optionally filtered by size. |
| `lookup_product_pricing` | `pricing` | Recorded cost and list price for one SKU. |
| `get_invoice_context` | `invoices`, `vendors`, `cash_accounts`, `payments` | Invoice/vendor facts plus account snapshots and payment rows for accounting review. |
| `get_lease_context` | `leases`, `cash_accounts`, `payments` | Lease terms plus account snapshots and payment rows for facilities review. |
| `get_customer_order_context` | `tickets`, `inventory`, `pricing` | Customer-safe details and list price for open merchandise tickets 101 and 103; excludes internal cost and account data. |

The tools return database records only. They do not infer a discount policy, assume payment rows settle a lease or invoice without reconciliation, promise inventory, approve or initiate money movement, contact customers/vendors, or update records. `get_customer_order_context` intentionally omits internal unit cost, cash balances, invoices, and payment rows.

## Install

From the HW 5 directory, install the server and agent dependencies into the same project-local environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt -r mcp_server/requirements.txt
```

`backend/requirements.txt` constrains PydanticAI to `>=1.0,<2` because this project uses its v1 MCP APIs. The install command includes `pydantic-ai-slim[openai,mcp]` and `mcp[cli]`; Python-dotenv is installed for the optional `.env` configuration.

The PydanticAI dependency provides the MCP client, OpenAI-compatible model support, and the local `FunctionModel` mock. `mcp_server/requirements.txt` keeps the server on the MCP Python SDK 1.x FastMCP interface.

## Connect and run

The project-root `.mcp.json` starts the MCP server over stdio using `.venv`. To launch it manually:

```sh
.venv/bin/python -m mcp_server.server
```

Run the Boss agent and specialist team locally without an API key or token use (default):

```sh
.venv/bin/python -m backend.runner "Review ticket 101" --ticket-id 101
```

Local mode uses PydanticAI's `FunctionModel` to execute a deterministic local model callback. It chooses an MCP tool from the ticket context, receives that tool's live read-only result from `data/campus_customs_new.db`, and builds a validated `AgentReply` from returned fields only. The normal PydanticAI agent graph, MCP calls, usage limits, and append-only audit logging still run; no LLM endpoint is contacted. The local responder omits internal unit costs from its evidence.

The production/grading path remains configured for only `gpt-6-luna` through Portkey. To opt into it, set `CAMPUS_CUSTOMS_LOCAL_MOCK=0` and provide `PORTKEY_API_KEY` in the shell or local gitignored `.env` file. The gateway URL defaults to `https://api.portkey.ai/v1`; set `PORTKEY_PROVIDER` or `PORTKEY_VIRTUAL_KEY` only if required by your Portkey workspace. There is no automatic fallback after a remote request fails: local mode is explicit and is the safe default so an exhausted key cannot consume attempts or loop between providers. Never put API keys in `.mcp.json` or source files.

## Backend API

Install the full requirements above, then start the local FastAPI app without making LLM requests:

```sh
CAMPUS_CUSTOMS_LOCAL_MOCK=1 .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The interactive API docs are at `http://127.0.0.1:8000/docs`. The app provides `GET /tickets`, `POST /tickets/{ticket_id}/run`, `GET /events?limit=50`, `POST /approvals`, `GET /cash/checking`, and `POST /reset`. Recent events include called MCP/delegation tool names and concise completion summaries. Cash approvals require the request fields `confirm: true` and `approved_by`; configure `CAMPUS_CUSTOMS_APPROVAL_TOKEN` to also require an `X-Approval-Token` header. Keep the server bound to localhost unless authentication is configured. Reset restores `data/campus_customs_new.db` from `data/campus_customs.db` and leaves the separate audit log intact.

## Vite frontend

The React + Vite + TypeScript dashboard lives in `frontend/` and calls FastAPI at `http://localhost:8000`. FastAPI allows the dashboard origin `http://localhost:5173`. With the API running in one terminal, install and start the frontend in another:

```sh
cd frontend
npm --cache ../.npm-cache install
npm run dev
```

The dashboard shows all three tickets and their status, runs the selected team through the SSE route, displays live agent actions and validated summaries, lists recent audit events, and refreshes the checking balance. Payments and purchases are recorded only through the explicit human-confirmation dialog. Create a type-checked production bundle with `npm run build`.
