# Campus Customs Agent Desk

A local Campus Customs support desk built with a read-only FastMCP database server, a five-role PydanticAI team, a FastAPI backend, and a React + Vite + TypeScript dashboard. The team uses `gpt-6-luna` through Portkey when explicitly enabled. Local mock mode is the default and uses live database tool results without contacting an LLM service or using API credits.

## Requirements

- Python 3.11 or newer (the project was verified with Python 3.14)
- Node.js 22 or newer and npm (verified with Node 24)
- macOS/Linux shell examples below; on Windows, use the corresponding `.venv` executables

## Setup

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt -r mcp_server/requirements.txt
cd frontend
npm install
cd ..
```

The frontend's `frontend/.npmrc` configures the npm mirror used for this project. The Python dependencies include FastAPI/Uvicorn, PydanticAI, and the MCP SDK/FastMCP server requirements. The equivalent one-line Python install is `.venv/bin/python -m pip install -r requirements.txt`. Use `.env.example` as a template only if you explicitly enable Portkey mode; keep the real `.env` local and untracked. The `.venv/`, `node_modules/`, npm cache, build output, Python caches, `.env`, and macOS `.DS_Store` files are excluded by `.gitignore`.

## Database files and reset

- `data/campus_customs.db` is the clean starter database and reset source.
- `data/campus_customs_new.db` is the working database used by the MCP server and backend. It is included in the repository so the submitted state is inspectable.
- Agents use read-only MCP tools; only the explicit FastAPI approval route can record a payment/purchase and debit a cash account.

Start the backend as described below, then restore every working database table to the original starter state:

```sh
curl -X POST http://localhost:8000/reset \
  -H 'Content-Type: application/json' \
  -d '{"confirm":true}'
```

The reset route requires `confirm: true`, can additionally require `X-Approval-Token` when `CAMPUS_CUSTOMS_APPROVAL_TOKEN` is configured, and preserves `output/audit_trail.json`. The initial checking balance is $3,400.00 as of 2026-08-31.

## MCP server

The MCP server is `mcp_server/server.py`; it connects to `data/campus_customs_new.db` and exposes read-only ticket, inventory, pricing, invoice, lease, and customer-safe context tools. The root `.mcp.json` contains the local stdio server configuration used by the desktop coding client. To launch the server manually:

```sh
.venv/bin/python -m mcp_server.server
```

The command runs the MCP stdio server in the foreground. The FastAPI agent runner starts the same server as a child process when it executes an agent team.

## Backend and agents

The backend defaults to the deterministic, database-backed PydanticAI local mock. Start FastAPI from the repository root:

```sh
CAMPUS_CUSTOMS_LOCAL_MOCK=1 .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open the API docs at `http://localhost:8000/docs`. The backend serves tickets and status, standard and SSE agent runs, recent audit events, checking balance, explicit payment/purchase approvals, and database reset. CORS is enabled for the Vite origin `http://localhost:5173`.

To run one ticket from the command line without using external model credits:

```sh
CAMPUS_CUSTOMS_LOCAL_MOCK=1 .venv/bin/python -m backend.runner \
  'Review the ticket using database evidence and recommend a safe next step.' \
  --ticket-id 101
```

The five agents are Boss, Inventory, Accounting, Facilities, and Customer Service. Any role may delegate to any other role; a five-agent depth limit and shared usage caps bound delegation loops. Graph-step metadata, tool names, and concise completion summaries are appended to `output/audit_trail.json` and are not cleared by database reset.

### Optional Portkey mode

To opt into the configured `gpt-6-luna` Portkey model, set `CAMPUS_CUSTOMS_LOCAL_MOCK=0` and provide `PORTKEY_API_KEY` in your shell or a local, gitignored `.env` file. Never commit `.env` or paste credentials into source files. Without that explicit opt-in, local mock mode makes no model API request.

## Frontend dashboard

In a second terminal, from the repository root:

```sh
cd frontend
npm run dev
```

Open `http://localhost:5173`. The dashboard lists tickets, streams agent actions/dialogue, summarizes agent work, shows recent audit events, and refreshes the checking balance. Payments and purchases require the human-confirmation dialog and use `POST /approvals`; agent runs do not make cash changes. To create and serve a production build:

```sh
npm run build
npm run preview
```

Design notes are in `output/design.md`; the ticket planning, actuals, cash ledger, and reflection are in `output/desk_tickets.html`.

## API route summary

| Method and path | Purpose |
| --- | --- |
| `GET /tickets` | Return tickets 101–103 and current status. |
| `POST /tickets/{ticket_id}/run` | Run the selected ticket and return its structured result. |
| `POST /tickets/{ticket_id}/run/stream` | Stream agent graph events; mark the workflow resolved after successful completion. |
| `GET /events?limit=50` | Return recent append-only agent events with called tool/delegation names and concise completion summaries. |
| `GET /cash/checking` | Return checking balance and snapshot date. |
| `POST /approvals` | Record a human-confirmed payment or purchase and debit checking. |
| `POST /reset` | Restore the working database from the clean starter database. |

See `output/harness.md` for the complete database schema, tool and role matrix, workflow limits, and safety notes.
