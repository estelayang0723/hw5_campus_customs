import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = 'http://localhost:8000'
type Ticket = { id: number; type: string; requester: string; subject: string; sku?: string | null; size?: string | null; qty?: number | null; status: string; notes?: string | null }
type AgentReply = { summary: string; evidence?: string[]; recommendation?: string; human_approval_needed?: boolean }
type FeedEvent = { type: string; message?: string; agent?: string; agent_role?: string; node_type?: string; tool_names?: string[]; reply?: AgentReply; ticket_id?: number; status?: string; [key: string]: unknown }
type AuditEvent = { agent?: string; agent_role?: string; event?: string; timestamp?: string; ticket_id?: number; message?: string; action?: string; tool_names?: string[]; [key: string]: unknown }
type ApprovalKind = 'payment' | 'purchase'

const ticketGlyph: Record<number, string> = { 101: '↗', 102: '⌂', 103: '▦' }
const money = (amount: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(amount)

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState(101)
  const [balance, setBalance] = useState<number | null>(null)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [running, setRunning] = useState(false)
  const [statusMessage, setStatusMessage] = useState('Ready when you are.')
  const [error, setError] = useState('')
  const [approvalOpen, setApprovalOpen] = useState(false)
  const [kind, setKind] = useState<ApprovalKind>('payment')
  const [amount, setAmount] = useState('')
  const [refId, setRefId] = useState('')
  const [approver, setApprover] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [approving, setApproving] = useState(false)

  const loadTickets = useCallback(async () => {
    const response = await fetch(`${API}/tickets`)
    if (!response.ok) throw new Error('Could not load tickets.')
    const data = await response.json() as { tickets: Ticket[] }
    setTickets(data.tickets)
  }, [])
  const loadBalance = useCallback(async () => {
    const response = await fetch(`${API}/cash/checking`)
    if (!response.ok) throw new Error('Could not load checking balance.')
    const data = await response.json() as { balance: number }
    setBalance(data.balance)
  }, [])
  const loadAudit = useCallback(async () => {
    const response = await fetch(`${API}/events?limit=25`)
    if (response.ok) {
      const data = await response.json() as { events: AuditEvent[] }
      setAudit(data.events)
    }
  }, [])

  useEffect(() => {
    Promise.all([loadTickets(), loadBalance(), loadAudit()]).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Backend unavailable.'))
    const timer = window.setInterval(() => { loadBalance().catch(() => undefined); loadTickets().catch(() => undefined); loadAudit().catch(() => undefined) }, 5000)
    return () => window.clearInterval(timer)
  }, [loadTickets, loadBalance, loadAudit])

  const currentTicket = tickets.find((ticket) => ticket.id === selected)
  const replies = useMemo(() => events.flatMap((event) => event.type === 'agent_completed' && event.reply ? [{ ...event.reply, agent: event.agent_role ?? 'agent' }] : []), [events])
  const approvalRequested = replies.some((reply) => reply.human_approval_needed) || events.some((event) => event.type === 'approval_needed')

  async function runTicket() {
    setError(''); setEvents([]); setRunning(true); setStatusMessage(`Starting the team on ticket ${selected}…`)
    try {
      const response = await fetch(`${API}/tickets/${selected}/run/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: `Review ticket ${selected}, consult only relevant specialists, use database evidence, and give a safe recommendation. Do not execute payments or purchases.` }),
      })
      if (!response.ok || !response.body) throw new Error(`Agent run could not start (${response.status}).`)
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { value, done } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? ''
        for (const frame of frames) {
          const line = frame.split('\n').find((item) => item.startsWith('data: ')); if (!line) continue
          const event = JSON.parse(line.slice(6)) as FeedEvent
          if (event.type === 'stream_done') continue
          setEvents((prior) => [...prior, event])
          if (event.message) setStatusMessage(event.message)
          if (event.type === 'ticket_resolved') { await Promise.all([loadTickets(), loadAudit()]); setStatusMessage(`Ticket ${selected} resolved.`) }
          if (event.type === 'run_failed') setError(event.message ?? 'Agent run failed.')
        }
      }
      await Promise.all([loadTickets(), loadBalance(), loadAudit()])
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Agent run failed.') }
    finally { setRunning(false) }
  }

  async function submitApproval(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setApproving(true)
    try {
      const response = await fetch(`${API}/approvals`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, amount: Number(amount), ref_id: refId ? Number(refId) : null, account: 'checking', approved_by: approver, confirm: true }) })
      const data = await response.json() as { detail?: string; balance?: number }
      if (!response.ok) throw new Error(data.detail ?? 'Approval was not recorded.')
      setBalance(data.balance ?? null); setApprovalOpen(false); setAmount(''); setRefId(''); setApprover(''); setConfirmed(false)
      setStatusMessage(`${kind === 'payment' ? 'Payment' : 'Purchase'} approved and recorded by ${approver}.`); await Promise.all([loadBalance(), loadAudit()])
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not record approval.') }
    finally { setApproving(false) }
  }

  return <div className="app-shell">
    <aside className="rail"><div className="brand-mark">CC</div><div className="rail-label">CAMPUS<br/>CUSTOMS</div><div className="rail-line"/><div className="rail-active">◫</div><div className="rail-foot">LOCAL<br/>DESK</div></aside>
    <main className="main-content">
      <header className="topbar"><div><div className="eyebrow">OPERATIONS / AGENT DESK</div><h1>Campus Customs <span>·</span> Workbench</h1></div><div className="connection"><i/> LOCAL SYSTEM <b>●</b></div></header>
      <section className="hero-row"><div><p className="eyebrow">MONDAY, AUGUST 31, 2026 <span className="dot-sep">•</span> SHIFT OVERVIEW</p><h2>Good morning, team.</h2><p className="hero-copy">Three requests need a careful read. Pick a ticket to brief the agent team.</p></div><div className="balance-card"><div className="balance-label"><span className="balance-icon">$</span> CHECKING BALANCE <span className="live-pill"><i/> LIVE</span></div><div className="balance-number">{balance === null ? '—' : money(balance)}</div><div className="balance-foot">Cash ledger · refreshed every 5 seconds</div></div></section>
      <div className="workspace-grid">
        <section className="ticket-panel panel"><div className="section-heading"><div><div className="eyebrow">INCOMING WORK</div><h3>Open tickets <span className="count">{tickets.filter((ticket) => ticket.status !== 'resolved').length}</span></h3></div><span className="subtle">UPDATED LIVE</span></div>
          <div className="ticket-list">{tickets.map((ticket) => <button key={ticket.id} className={`ticket-card ${selected === ticket.id ? 'selected' : ''}`} onClick={() => setSelected(ticket.id)} disabled={running} aria-pressed={selected === ticket.id}>
            <span className={`ticket-glyph glyph-${ticket.id}`}>{ticketGlyph[ticket.id]}</span><span className="ticket-main"><span className="ticket-meta">#{ticket.id} <span>·</span> {ticket.type.replaceAll('_', ' ')}</span><strong>{ticket.subject}</strong><span className="ticket-requester">{ticket.requester}{ticket.sku ? ` · ${ticket.qty ?? ''} × ${ticket.sku}${ticket.size ? ` / ${ticket.size}` : ''}` : ''}</span></span><span className={`status-tag ${ticket.status === 'resolved' ? 'resolved' : ''}`}><i/>{ticket.status}</span><span className="chevron">›</span>
          </button>)}</div>
          <div className="selected-note"><span className="note-pin">✳</span><div><b>Selected briefing</b><p>{currentTicket?.notes || 'Ticket details will appear here.'}</p></div></div>
          <button className="run-button" onClick={runTicket} disabled={running || !currentTicket}><span>{running ? <span className="spinner"/> : '▶'}</span>{running ? 'Team is working…' : 'Run agent team'}<span className="button-arrow">↗</span></button>
          <p className="run-footnote">Agents gather evidence and recommend actions. Money movement always waits for your approval.</p>
        </section>

        <section className="activity-panel panel"><div className="section-heading"><div><div className="eyebrow">LIVE WORKSTREAM</div><h3>Agent activity</h3></div><span className={`live-pill ${running ? 'active' : ''}`}><i/>{running ? ' RUNNING' : ' READY'}</span></div>
          <div className="stream-status"><span className="status-spark">✳</span><span>{statusMessage}</span></div>
          <div className="activity-feed" aria-live="polite" aria-label="Live agent actions">
            {events.length === 0 && <div className="empty-feed"><div className="empty-orbit">✳</div><b>Your workstream starts here</b><p>Select a ticket and run the agent team to watch evidence gathering and decisions appear live.</p></div>}
            {events.map((event, index) => <div className="feed-item" key={`${index}-${event.type}`}><div className={`feed-avatar ${(event.agent_role ?? event.agent) === 'boss' ? 'boss' : ''}`}>{(event.agent_role ?? event.agent ?? event.type.replace('agent_', '')).slice(0, 2).toUpperCase()}</div><div className="feed-content"><div className="feed-title"><strong>{(event.agent_role ?? event.agent ?? (event.type === 'ticket_resolved' ? 'Desk update' : 'Agent team')).replaceAll('_', ' ')}</strong><time>{event.node_type?.replace('Node', '') ?? (event.type === 'ticket_resolved' ? 'COMPLETE' : 'LIVE')}</time></div><p>{event.message ?? event.type.replaceAll('_', ' ')}</p>{event.tool_names && event.tool_names.length > 0 && <div className="tool-chips">{event.tool_names.map((tool) => <span key={tool}>⌘ {tool}</span>)}</div>}{event.reply && <div className="reply-card"><b>Decision brief</b><p>{event.reply.summary}</p>{event.reply.evidence?.length ? <ul>{event.reply.evidence.map((item, i) => <li key={i}>{item}</li>)}</ul> : null}{event.reply.recommendation && <p><b>Recommended next step:</b> {event.reply.recommendation}</p>}{event.reply.human_approval_needed && <span className="approval-needed">Human approval needed</span>}</div>}</div></div>)}
          </div>
          {approvalRequested && <div className="approval-callout"><div><b>Human approval required</b><p>Review the recommendation, then record the approved outflow below.</p></div><button onClick={() => setApprovalOpen(true)}>Review approval <span>↗</span></button></div>}
        </section>
      </div>

      <section className="lower-grid"><div className="panel summary-panel"><div className="section-heading"><div><div className="eyebrow">TEAM BRIEF</div><h3>What each agent did</h3></div><span className="subtle">{replies.length} REPORT{replies.length === 1 ? '' : 'S'}</span></div>{replies.length ? <div className="summary-list">{replies.map((reply, index) => <article className="summary-row" key={`${reply.agent}-${index}`}><span className={`summary-avatar ${reply.agent === 'boss' ? 'boss' : ''}`}>{reply.agent.slice(0, 1).toUpperCase()}</span><div><b>{reply.agent.replaceAll('_', ' ')}</b><p>{reply.summary}</p></div></article>)}</div> : <div className="summary-placeholder">Agent summaries will collect here after a run.</div>}</div>
        <div className="panel audit-panel"><div className="section-heading"><div><div className="eyebrow">APPEND-ONLY RECORD</div><h3>Recent audit events</h3></div><span className="subtle">LATEST {Math.min(audit.length, 25)}</span></div>{audit.length ? <div className="audit-list">{audit.slice(0, 5).map((item, i) => <div className="audit-row" key={i}><span className="audit-dot"/><div><b>{item.agent_role ?? item.agent ?? item.event ?? item.action ?? 'Agent event'}</b><span>{item.message ?? (item.ticket_id ? `Ticket #${item.ticket_id}` : 'Recorded agent activity')}</span>{item.tool_names?.length ? <div className="tool-chips">{item.tool_names.map((tool) => <span key={tool}>⌘ {tool}</span>)}</div> : null}</div><time>{item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'LOG'}</time></div>)}</div> : <div className="summary-placeholder">No agent events recorded yet.</div>}</div></section>
      {error && <div className="error-banner" role="alert"><b>Something needs attention</b><span>{error}</span><button onClick={() => setError('')}>Dismiss</button></div>}
      <footer>Campus Customs agent desk <span>·</span> Local development build <span>·</span> All financial actions require human approval</footer>
    </main>

    {approvalOpen && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setApprovalOpen(false) }}><section className="approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-title"><button className="modal-close" onClick={() => setApprovalOpen(false)} aria-label="Close">×</button><div className="eyebrow">HUMAN CHECKPOINT</div><h2 id="approval-title">Approve a cash action</h2><p className="modal-intro">This records a payment or purchase and immediately updates the checking ledger. Confirm the details before submitting.</p><form onSubmit={submitApproval}><label>Action<select value={kind} onChange={(event) => setKind(event.target.value as ApprovalKind)}><option value="payment">Payment</option><option value="purchase">Purchase</option></select></label><label>Amount (USD)<input required type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00"/></label><label>Reference ID <span className="optional">optional</span><input type="number" min="1" value={refId} onChange={(event) => setRefId(event.target.value)} placeholder="Invoice or record ID"/></label><label>Approved by<input required value={approver} onChange={(event) => setApprover(event.target.value)} placeholder="Your name"/></label><label className="confirm-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)}/><span>I reviewed this amount and authorize its recording and deduction from checking.</span></label><button className="run-button" type="submit" disabled={approving || !confirmed}>{approving ? 'Recording…' : `Confirm ${kind}`}<span className="button-arrow">↗</span></button></form></section></div>}
  </div>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
