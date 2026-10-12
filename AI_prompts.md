# HW5 — AI Prompts

## Problem 1: Vibe coder prompts

help me create an AI_prompts.md file for our AI HW5 assignment so we can keep track of all our prompts as we build the campus customs multi-agent shop

### Progress log

- Created this prompt log at the beginning of the assignment and kept the subsequent problem prompts and progress notes here.


## Problem 2 — Campus Customs database harness

### User prompt

> Please help me with Problem 2: Study the Campus Customs database. First, make a copy of the original database file `data/campus_custums.db` to `data/campus_custums_new.db` as requested. Then, inspect every table and its fields in the database, study the open tickets, and create an `output/harness.md` file that lists each table, its fields, and a short description of why that table matters for the agents. Also, remember to log our progress and my prompt in `AI_prompts.md` for Problem 2 following the required format.

### Progress log

- Inspected the HW 5 directory and found the supplied database at `data/campus_customs.db`; the requested source spelling `campus_custums.db` was not present. Used the existing database as the source and created the specifically requested destination name `data/campus_custums_new.db`.
- Inspected all 9 tables, their columns, SQLite types, nullability, primary keys, and declared foreign keys.
- Reviewed the 3 open tickets and their relevant inventory, pricing, lease, invoice, vendor, cash-account, and payment records.
- Created `output/harness.md` with the full schema reference, agent relevance for each table/field, open-ticket findings, and data-handling notes.
- No database records were modified; only a copy of the original database was created.


## Problem 3 — Build the MCP server

### User prompt

> Please help me with Problem 3: Build the MCP server. Inside `mcp_server/`, write an MCP server using FastMCP that connects to `data/campus_customs_new.db`. Create three core tools tailored to help resolve the three open tickets in the database (tickets 101, 102, and 103). Do not invent data; only query what is in the database. Update `output/harness.md` to list each of the three MCP tools, specifying which table it reads, which specific open ticket (101, 102, or 103) it helps unlock, and one precise sentence explaining why that tool is right for that ticket. Also create a `mcp_server/README.md` file explaining what the MCP server is for, which database file it uses, and detailing its three tools. Finally, update `AI_prompts.md` to log Problem 3.

### Progress log

- Inspected the Problem 2 copy (`data/campus_custums_new.db`), then created the correctly spelled Problem 3 target (`data/campus_customs_new.db`) from it and confirmed the three open tickets and relevant linked records.
- Implemented three ticket-specific FastMCP tools in `mcp_server/server.py`; each uses parameterized, read-only SQLite queries against `data/campus_customs_new.db`.
- Added `mcp_server/README.md` with the server purpose, database path, tool/table/ticket mapping, and launch instructions.
- Updated `output/harness.md` with each tool's source tables, target open ticket, and a ticket-specific rationale.
- Recorded this original prompt and progress in `AI_prompts.md`.
- At the end of Problem 3, the default Python environment did not have `mcp` installed, so runtime verification was deferred; Problem 4 installs the SDK in the local `.venv` and records successful protocol tests.


## Problem 4 — Connect and smoke-test the MCP server

### User prompt

> roblem 4: Add the MCP server to vibe coder and test each tool. First, create a `.mcp.json` file at the project root with the correct local configuration to connect our MCP server. Then, test each of the three MCP tools, and save the testing evidence in `output/mcp_smoke.json` containing the prompt asked, the tool name, and the tool output (which must match values in `data/campus_customs_new.db`). Finally, update `AI_prompts.md` to log Problem 4.

### Progress log

- Created the project-root `.mcp.json` entry `campus-customs` using the local `.venv` Python executable and the MCP server script path.
- Installed the FastMCP-compatible MCP Python SDK (`mcp` 1.x) in the project-local `.venv`; pinned `mcp[cli]` to `<2` in `mcp_server/requirements.txt` because MCP SDK 2.x no longer exposes the required FastMCP import path.
- Connected to the server over stdio using an MCP client, confirmed all three tools are registered, and invoked each tool.
- Saved each actual test prompt, tool name, and structured tool output in `output/mcp_smoke.json`.
- Compared the key returned ticket, inventory, invoice, lease, cash, payment, and pricing values against read-only queries to `data/campus_customs_new.db`; all assertions passed.
- Updated `mcp_server/README.md` with local environment setup and project configuration details.


## Problem 5 — Build the Campus Customs agent team

### User prompt

> Problem 5: Build the agent team and grow the MCP tools. Using PydanticAI, build the agent team for Campus Customs with five roles: Boss, Inventory, Accounting, Facilities, and Customer Service, giving them full connectivity and agent loops using `PORTKEY_API_KEY` and only `gpt-6-luna`. Put the individual agent prompts in `backend/prompts/` (one file per agent), data types in `backend/models.py`, and the agent implementation files under `backend/`. Add any additional tools the agents need to our MCP server communicating over `data/campus_customs_new.db`. Wire the agents to append to `output/audit_trail.json` on each agent-loop step without wiping it. Update `output/harness.md` to list each agent, each MCP tool with its table, and a short safety section covering guardrails for customers/money and token limits. Update `mcp_server/README.md` to match the current tool list, and log Problem 5 in `AI_prompts.md`.

### Progress log

- Added five role-specific prompt files and Pydantic data types for validated requests, responses, and audit records.
- Implemented a Boss agent with specialist delegation plus Inventory, Accounting, Facilities, and Customer Service agents; share the stdio MCP server connection with role-filtered specialist tools and the fixed `gpt-6-luna` model routed through Portkey using `PORTKEY_API_KEY`.
- Added six read-only MCP tools for open-ticket triage, inventory lookup, SKU pricing, invoice/accounting context, lease/facilities context, and customer-safe merchandise context; all query `data/campus_customs_new.db`.
- Added a JSON-array audit appender that locks the file and appends one metadata-only record per PydanticAI graph node and agent invocation, preserving prior records and omitting prompt/customer content.
- Set workflow-wide limits for model requests, tool calls, and input/output/total tokens; added customer and money guardrails to prompts and harness documentation. Specialist MCP toolsets are role-filtered, including customer-safe tool output that excludes internal unit cost and account data.
- Updated `output/harness.md` and `mcp_server/README.md` with the five roles and full MCP tool list.
- At the time Problem 5 was first implemented, PydanticAI runtime verification was pending because package-index DNS resolution failed; this was resolved in the later package-install section below.


## Local PydanticAI Mock/Fallback

### User prompt

> Since my Portkey credits are exhausted and I cannot top up, please help me implement a local Mock/Fallback mechanism for PydanticAI in the backend. It should keep `gpt-6-luna` and Portkey configuration in the code for grading compliance, but intercept API calls during local execution to return valid, database-consistent responses based on `data/campus_customs_new.db` so that all tests, agent loops, and `audit_trail.json` generations can run successfully without burning tokens.

### Progress log

- Added a local PydanticAI `FunctionModel` mode selected by `CAMPUS_CUSTOMS_LOCAL_MOCK` (enabled by default); it makes no network/API request and requires no Portkey key.
- The mock selects only tools available to the active role, calls the existing read-only MCP toolset, and formats a validated `AgentReply` from actual tool-return values; internal unit cost is excluded from displayed evidence.
- Kept the fixed `gpt-6-luna` model name and full Portkey provider/header configuration for grading and opt-in remote execution (`CAMPUS_CUSTOMS_LOCAL_MOCK=0`).
- Documented local and Portkey run modes in `mcp_server/README.md` and `output/harness.md`; added explicit ticket context to runner prompts when `--ticket-id` is supplied.
- Installed PydanticAI and MCP in `.venv` in the package-install step below; all three local agent graph paths now execute successfully without Portkey calls.


## Install backend packages and verify local agent graphs

### User prompt

> Please help me install the required Python packages (including pydantic-ai and mcp) into our local virtual environment (.venv) so that we can run the agent graph and verify our code properly. Please also write down the exact pip install commands in the terminal or README if needed.

### Progress log

- Constrained `pydantic-ai-slim[openai,mcp]` to `>=1.0,<2` to retain compatibility with this project's PydanticAI v1 `MCPToolset` API; the latest 2.x release uses a different MCP dependency line.
- Installed dependencies into the existing Python 3.14 `.venv` with `.venv/bin/python -m pip install -r backend/requirements.txt -r mcp_server/requirements.txt`.
- Verified installed versions: PydanticAI 1.107.7, MCP SDK 1.30.0, FastMCP client library 3.4.8, and OpenAI client 3.29.0; PydanticAI, FastMCP, backend agent modules, and local `FunctionModel` imports succeeded.
- Ran the local agent graph for tickets 101, 102, and 103. The live MCP results reported 0 size-S tees for ticket 101, a $2,400 rent due 2026-09-02 and $3,400 checking snapshot dated 2026-08-31 for ticket 102, and 8 size-M hoodies for a request of 20 for ticket 103.
- Confirmed all runs appended graph events to `output/audit_trail.json`; its JSON array remains valid. Updated `mcp_server/README.md` with the exact setup/install commands.


## Problem 6 — Plan the three tickets

### User prompt

> Problem 6: Plan the three tickets. Create an `output/desk_tickets.html` file that features one tab per ticket for the three open tickets (101, 102, and 103), plus empty Cash and Reflection tabs with a "coming later" note. For each ticket tab, write an Expected section in my own words covering: who the Boss should call first and why, the expected agent delegations (avoiding a generic "Boss calls everyone" approach), and which specific MCP tools are expected to be used. Leave space for an Actual section to be filled in later. Finally, log Problem 6 in `AI_prompts.md`.

### Progress log

- Read the three open ticket rows and checked the ticket-specific MCP tools, specialist tool access, and agent safety prompts.
- Created `output/desk_tickets.html` with keyboard-accessible tabs for tickets 101, 102, 103, Cash, and Reflection.
- Added first-person Expected plans with a specific first specialist consultation, purpose-based follow-up delegations, and ticket-specific MCP tool names/arguments; left a blank Actual notes area in each ticket tab.
- Added empty Cash and Reflection tabs with “Coming later” notes and logged the original Problem 6 prompt and progress here.


## Problem 7 — Backend routes

### User prompt

> Problem 7: Backend routes. In `backend/main.py`, use FastAPI to implement the required routes: return the three tickets and their status, take a ticket id and run the agent team on it, return recent agent events for dashboard refreshing, approve a payment or purchase to update cash, return the current checking balance from cash_accounts, and reset the database to original values. Also, update `output/harness.md` to list each route (its URL and what it does) in one line. Finally, log Problem 7 in `AI_prompts.md`.

### Progress log

- Added `backend/main.py` with six FastAPI routes for ticket listing, ticket agent runs, recent audit events, explicit cash approvals, checking balance, and resetting the working database.
- Cash approvals validate explicit confirmation and approver, then atomically append a `payments` row and debit the chosen `cash_accounts` row; insufficient balances fail without changing the database. An optional `CAMPUS_CUSTOMS_APPROVAL_TOKEN` can require an approval header.
- Reset uses SQLite's backup API to restore all tables from `data/campus_customs.db`; it leaves the separate append-only audit trail intact.
- Added FastAPI and Uvicorn requirements, documented the local API launch command, and listed each route in `output/harness.md`.
- FastAPI 0.143.0 installed successfully after DNS became available. TestClient checks passed for all six routes, including ticket 103's mock agent run and a confirmed $1 test payment; `/reset` restored checking to $3,400 and cleared the test payment row.
- Created the vanilla Vite 8.3.4 frontend, installed its 15 npm packages with zero reported vulnerabilities, and confirmed `npm run build` succeeds. The Vite proxy targets the loopback FastAPI server; UI fonts use local system fallbacks.
- `pip check` reports no broken requirements. Both web-app launch commands are documented in `mcp_server/README.md`.


## Problem 8 — Agent dashboard

### User prompt

> Problem 8: Agent dashboard. Build the frontend dashboard in frontend/ using React + Vite + TypeScript to interact with our FastAPI backend at http://localhost:8000. Ensure the backend allows CORS for the frontend origin (http://localhost:5173). The dashboard should: list all three tickets, let the user pick one ticket and trigger the agent team, show real-time agent actions and dialogue during the run, mark the ticket as resolved upon completion, show a summary of what each agent did, allow human approval for payments or purchases, and display the live checking balance. Also, create output/design.md detailing the layout, design choices, and user experience, and log Problem 8 in AI_prompts.md.

### Progress log

- Replaced the previous static Vite page with a responsive React + TypeScript dashboard, including ticket selection/status, streamed agent activity and dialogue, per-agent summaries, recent audit events, live checking balance, and an explicit human-confirmation dialog for payments or purchases.
- Confirmed FastAPI CORS allows `http://localhost:5173` and added the SSE run route to the backend harness route list. Successful agent completion marks the selected ticket resolved; failed runs remain unresolved.
- Added `output/design.md` with the layout, visual choices, interaction and safety design, and responsive/accessibility behavior.
- Updated `mcp_server/README.md` with the React/Vite frontend commands and dashboard behavior.
- TypeScript type-check and Vite production build pass. Python compile succeeds; FastAPI CORS preflight returns `http://localhost:5173`; SSE runs for tickets 101, 102, and 103 each include agent starts/actions/completions, structured dialogue, `ticket_resolved`, and `stream_done`.
- After the three-ticket integration check, `/reset` restored the original open-ticket state and checking balance ($3,400 dated 2026-08-31). No payment was recorded by the run.
- Started FastAPI and Vite together and confirmed the HTTP ticket-list endpoint returns all three tickets while the Vite server serves the React entrypoint on port 5173.


## Problem 9 — Resolve the tickets

### User prompt

> Problem 9: Resolve the tickets. First, reset the working database `data/campus_customs_new.db` to its clean initial state and note the starting checking balance. Then, run all three tickets (101, 102, 103) through our agent team until each is fully resolved. Update `output/desk_tickets.html` by filling in the Actual section on each ticket tab and itemizing the money flow (starting balance, per-ticket changes with amounts, and ending checking balance matching `cash_accounts`) on the Cash tab. Save `output/resolved_tickets.json` with ticket details, outcomes, agent contributions, and approvals. Create `output/resolved_board.html` showing the board state for each resolved ticket. Append the real run to `output/audit_trail.json`, finalize `output/harness.md` to comprehensively cover tables, tools, agents, routes, dashboard, and safety, and log Problem 9 in `AI_prompts.md`.

### Progress log

- Reset `data/campus_customs_new.db` from the original database before running any ticket; recorded the starting checking balance of $3,400.00 dated 2026-08-31.
- Ran tickets 101, 102, and 103 through the PydanticAI team in local mock mode. All three workflows completed and the backend marked each ticket `resolved`; run IDs and graph-step records were appended to `output/audit_trail.json`.
- Recorded ticket facts, actual agent-role contributions, run IDs, outcomes, approval state, and per-ticket cash changes in `output/resolved_tickets.json`; filled each Actual section and the Cash tab in `output/desk_tickets.html`; created `output/resolved_board.html`.
- No payment or purchase was approved or recorded. Each agent result flags human approval for financial/customer/policy actions; therefore each ticket's cash change is $0.00, the payments table remains empty, and ending checking is $3,400.00, matching `cash_accounts`. The workflow status is resolved while outstanding real-world fulfillment/payment/discount decisions are clearly identified for human follow-up.
- Expanded `output/harness.md` to summarize all nine tables and fields, MCP tools, agents, routes, dashboard usage, actual outcomes, cash reconciliation, and safety controls.


## Problem 10 — Reflection

### User prompt

> Problem 10: Reflection. Open output/desk_tickets.html and fill the Reflection tab with a detailed, thorough analysis tied specifically to our app and the three tickets we ran. It must include: an evaluation of the agents' performance on each ticket and why, a comparison between Actual outcomes and the Expected plans from Problem 6, an analysis of what would have been simpler with a single agent with tools and why, three new potential problems for Campus Customs that our current agent team and tools could solve, and three new potential problems that our current setup could not solve along with the required new tools and agents. Finally, log Problem 10 in AI_prompts.md.

### Progress log

- Filled the Reflection tab with ticket-specific agent performance analysis for 101, 102, and 103, grounded in the Problem 6 Expected plans, Problem 9 Actual records, and the database facts.
- Compared expected delegation sequences with the actual roles and evidence; noted that current audit events do not record MCP tool names, so exact per-call tool verification is limited.
- Evaluated a single-agent alternative against specialist delegation, including reduced loop overhead and the tradeoff in role-based access boundaries.
- Documented three additional read-only tasks supported by the existing inventory, invoice, and lease tools, plus three unsupported operational problems and the agents/integrations needed to handle them safely.
- Called out the local mock's generic response text and the distinction between an agent workflow marked resolved and actual business fulfillment; added concrete improvement opportunities tied to this app.


## Problem 11 — Submit to GitHub

### User prompt

> Problem 11: Submit to GitHub. Ensure that my public repository URL `https://github.com/estelayang0723/hw5_campus_customs.git` is accurately saved into `output/github_url.txt`. Verify that `.env` is properly excluded via `.gitignore`, both database files (`campus_customs.db` and `campus_customs_new.db`) under `data/` are included, and the root `README.md` clearly details the setup, database reset, MCP server, backend, and frontend execution steps. Finally, make sure Problem 11 is properly logged in `AI_prompts.md`.

### Progress log

- Saved the exact public repository URL in `output/github_url.txt`.
- Confirmed `.env` is ignored and added `.DS_Store` to the ignore rules; database files are not excluded.
- Added a root README covering Python/npm setup, clean database reset, MCP stdio server, local/mock agent run, FastAPI backend, optional Portkey configuration, frontend launch/build, routes, and safety notes.
- Initial repository inspection found no local `.git` metadata; initialized a local repository, added the requested GitHub URL as `origin`, and staged the project while excluding `.env`, caches, virtual environments, and build output.
- Verified `.env` is ignored and absent from the remote tree; verified `data/campus_customs.db` and `data/campus_customs_new.db` are both committed. The URL, root README, and Problem 11 log are present in `main`.
- Committed and pushed the submission to the public repository's `main` branch; remote HEAD is commit `a988e85` (submission commit).


## Post-submission corrections

### User prompt

> 帮我修正，修正后更新我的github

### Progress log

- Restored the complete per-problem prompt and progress sections while preserving the original Problem 1 prompt supplied by the user.
- Added `tool_names` and a concise agent completion summary to new append-only audit records; `GET /events` now returns these fields, and the dashboard displays tool names from recent audit events. Older audit entries remain intact.
- Added delegation from every agent role to any other role through `consult_specialist`; a five-agent depth limit and shared PydanticAI usage limits bound loops.
- Added root `requirements.txt` and a secret-free `.env.example`, and updated the setup documentation.
- Reset the working database from the original and reran all three ticket workflows in local mock mode; the final run IDs in the Problem 9 artifacts point to these runs, whose audit records contain agent tool/delegation names and completion summaries. No Portkey calls or cash approvals were made. The artifacts distinguish completed review workflows from pending real-world payment, replenishment, customer, and discount decisions.
