# Problem 8 — Agent Dashboard design

## Layout

The dashboard uses a persistent, narrow forest-green navigation rail and a spacious operations canvas. The top bar identifies the local agent desk and connection. A shift overview pairs the greeting and brief with a prominent checking-balance card. The main workspace places the three-ticket queue beside the live agent workstream. Below it, separate panels summarize each agent's work and show the latest append-only audit events.

## Visual choices

- A quiet cream background, deep green navigation, and restrained sage accents connect the dashboard to a campus retail operations desk without competing with the ticket content.
- Ticket-specific glyphs and status pills make selection and resolution easy to scan. Selected tickets have a tinted surface and a clear left-edge accent.
- Compact mono labels distinguish IDs, event types, and live states from readable ticket and agent summaries.
- The activity feed uses separate agent badges, tool chips, and structured decision briefs. It renders ordinary text through React, so database content is escaped rather than interpreted as markup.

## Interaction and safety

- The queue and checking balance load from FastAPI and refresh every five seconds. The selected ticket can be run with one explicit action.
- A server-sent event stream shows agent starts, graph actions, MCP tool names, final structured replies, failures, and successful resolution as they happen.
- After completion, the queue refreshes its status and the team brief collects each completed agent's summary. A ticket becomes resolved only after the backend receives a successful validated agent result.
- Payment or purchase recording is separated into a human checkpoint dialog. It requires action type, positive amount, approver name, and a checked authorization statement before posting to `/approvals`; the API updates cash only after that confirmation and its own balance checks.
- Financial actions remain explicit and traceable. The dashboard never submits a payment as part of an agent run.

## Responsive behavior and accessibility

The two-column ticket/workstream layout collapses to a single column on tablet and phone widths. Ticket selection uses real buttons with an exposed pressed state; activity updates are announced through a polite live region. Approval is a labeled modal dialog with keyboard-operable form controls, focus-visible input styling, and a clear cancel affordance. Status and progress are conveyed with text as well as color.
