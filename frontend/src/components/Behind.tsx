import { useEffect, useState } from 'react'
import { AGENTS, api } from '../api'
import { AgentTag } from './ui'

const EVENT_TONE: Record<string, string> = {
  moderation: 'green', off_topic_redirect: '', output_blocked: 'red', prompt_leak_blocked: 'red', budget_blocked: 'red',
  rate_limited: 'red', login_failed: 'red', demo_login_refused: 'red', signup: 'green', login: 'green', demo_login: 'green',
}

const usd = (n: number, d = 5) => `$${(n ?? 0).toFixed(d)}`
const num = (n: number) => (n ?? 0).toLocaleString()

export default function Behind() {
  const [usage, setUsage] = useState<any>(null)
  const [activity, setActivity] = useState<any[]>([])
  const [mods, setMods] = useState<any[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    const load = () => {
      api.usage().then(setUsage)
      api.activity(30).then(setActivity)
      api.moderation().then(setMods)
      api.auditEvents(40).then(setEvents)
    }
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="behind">
      <section className="card">
        <h2>The agent team</h2>
        <p className="muted small">
          Code decides who runs next; agents never call each other. Every agent returns a typed answer that code checks
          before anyone sees it.
        </p>
        <TeamDiagram />
      </section>

      <section className="card">
        <h2>Tokens and cost (measured)</h2>
        {usage && (
          <>
            <div className="stats">
              <Stat label="Agent runs" value={num(usage.runs)} />
              <Stat label="Input tokens" value={num(usage.totals.input_tokens)} />
              <Stat label="Cached input" value={num(usage.totals.cached_input_tokens)} />
              <Stat label="Output tokens" value={num(usage.totals.output_tokens)} />
              <Stat label="Total cost" value={usd(usage.totals.cost_usd, 4)} />
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Runs</th>
                  <th>Avg input</th>
                  <th>Avg cached</th>
                  <th>Avg output</th>
                  <th>Avg cost / run</th>
                  <th>Avg time</th>
                  <th>Total cost</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(AGENTS)
                  .filter((a) => usage.by_agent[a])
                  .map((a) => {
                    const r = usage.by_agent[a]
                    return (
                      <tr key={a}>
                        <td>
                          <AgentTag agent={a} />
                        </td>
                        <td>{r.runs}</td>
                        <td>{num(r.avg_input)}</td>
                        <td>{num(r.avg_cached)}</td>
                        <td>{num(r.avg_output)}</td>
                        <td>{usd(r.avg_cost_usd, 6)}</td>
                        <td>{r.avg_seconds}s</td>
                        <td>{usd(r.cost_usd, 4)}</td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
            <p className="muted tiny">
              From output/usage_log.jsonl: token counts reported by the API on every run, priced with data/prices.json.
            </p>
          </>
        )}
      </section>

      <div className="behind-cols">
        <section className="card">
          <h2>Recent agent runs</h2>
          {activity.map((a, i) => {
            const id = `${a.run_id}-${i}`
            return (
              <div key={id} className="run">
                <button className="run-head" onClick={() => setOpen(open === id ? null : id)}>
                  <AgentTag agent={a.agent} />
                  <span className="muted tiny">{a.time?.slice(11, 19)}</span>
                  <span className="tiny">{a.trigger}</span>
                  {a.error && <span className="pill red">error</span>}
                  {a.code_layer_removed?.length > 0 && <span className="pill red">cleaned {a.code_layer_removed.length}</span>}
                  {a.model_flagged_suspicious?.length > 0 && <span className="pill red">flagged</span>}
                  {a.off_topic && <span className="pill">off-topic declined</span>}
                  {a.blocked && <span className="pill red">{a.blocked}</span>}
                  {a.tokens && (
                    <span className="muted tiny right">
                      {num(a.tokens.input_tokens + a.tokens.output_tokens)} tok · {usd(a.tokens.cost_usd, 5)}
                    </span>
                  )}
                </button>
                {open === id && (
                  <div className="run-body">
                    {a.tool_calls?.length > 0 && (
                      <>
                        <div className="label">Tool calls</div>
                        <ol>
                          {a.tool_calls.map((t: any, j: number) => (
                            <li key={j}>
                              <code>
                                {t.tool}({Object.entries(t.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')})
                              </code>
                              <div className="muted tiny">→ {String(t.result)}</div>
                            </li>
                          ))}
                        </ol>
                      </>
                    )}
                    {a.code_layer_removed?.length > 0 && (
                      <>
                        <div className="label">Removed by the code layer before the AI read it</div>
                        <ul>
                          {a.code_layer_removed.map((r: any, j: number) => (
                            <li key={j} className="tiny">
                              <b>{r.kind}</b> in {r.source}: “{r.text}”
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {a.model_flagged_suspicious?.length > 0 && (
                      <>
                        <div className="label">Flagged as suspicious by the agent</div>
                        <ul>{a.model_flagged_suspicious.map((t: string, j: number) => <li key={j} className="tiny">{t}</li>)}</ul>
                      </>
                    )}
                    <div className="label">Answer</div>
                    <pre>{JSON.stringify(a.output ?? a.error, null, 2)}</pre>
                  </div>
                )}
              </div>
            )
          })}
        </section>

        <section className="card">
          <h2>Safety audit trail</h2>
          <p className="muted tiny">
            From output/audit_trail.jsonl (append-only): every moderation decision, off-topic redirect, blocked reply,
            sign-in, and limit. Passwords and tokens are never logged; emails are masked.
          </p>
          {events.map((ev, i) => (
            <div key={i} className="mod">
              <div className="mod-top">
                <span className={`pill ${ev.event === 'moderation' ? (ev.verdict === 'hide' ? 'red' : 'green') : EVENT_TONE[ev.event] ?? ''}`}>{ev.event === 'moderation' ? (ev.verdict === 'hide' ? 'hidden' : 'allowed') : ev.event.replace(/_/g, ' ')}</span>
                <span className="muted tiny">{ev.time?.slice(11, 19)}</span>
                {ev.layer && <span className="tiny">by {ev.layer === 'code' ? 'code screen' : ev.layer === 'agent' ? 'Moderator agent' : ev.layer}</span>}
                {ev.category && ev.category !== 'none' && <span className="tiny">{ev.category}</span>}
                {ev.off_topic && <span className="tiny">off-topic</span>}
              </div>
              {ev.text && <div className="mod-text">“{ev.text}”</div>}
              {(ev.email || ev.reason || ev.agent) && (
                <div className="muted tiny">{[ev.email, ev.agent, ev.event === 'moderation' ? null : ev.reason].filter(Boolean).join(' · ')}</div>
              )}
            </div>
          ))}
        </section>

        <section className="card">
          <h2>Moderation log</h2>
          <p className="muted tiny">Every message checked. Code catches contact info, links and AI instructions for free; the Moderator agent judges the rest.</p>
          {mods.map((m) => (
            <div key={m.id} className={`mod ${m.verdict}`}>
              <div className="mod-top">
                <span className={`pill ${m.verdict === 'hide' ? 'red' : 'green'}`}>{m.verdict === 'hide' ? 'hidden' : 'allowed'}</span>
                <span className="tiny">{m.category}</span>
                <span className="muted tiny">by {m.layer === 'code' ? 'code filter' : m.layer === 'agent' ? 'Moderator agent' : m.layer}</span>
                <span className="muted tiny right">{m.display_name}</span>
              </div>
              <div className="mod-text">“{m.text}”</div>
              {m.verdict === 'hide' && <div className="muted tiny">{m.reason}</div>}
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-v">{value}</div>
      <div className="muted tiny">{label}</div>
    </div>
  )
}

// The agent hand-off diagram. Solid colored boxes are the five AI agents; gray outlines are plain code (no AI);
// blue outlines are people. Arrows run on right angles with their label on a white chip, so nothing crosses.
type Kind = 'agent' | 'code' | 'people' | 'blocked'

function TeamDiagram() {
  const INK = '#2b3550'
  const node = (x: number, y: number, w: number, h: number, kind: Kind, title: string, sub: string, color = '#051230') => {
    const agent = kind === 'agent'
    const stroke = kind === 'people' ? '#3f7484' : kind === 'blocked' ? '#a8321e' : kind === 'code' ? '#9aa3b5' : color
    const fill = agent ? color : kind === 'people' ? '#eef6f8' : kind === 'blocked' ? '#fdeeea' : '#ffffff'
    const titleFill = agent ? '#ffffff' : kind === 'people' ? '#24505c' : kind === 'blocked' ? '#a8321e' : '#051230'
    const subFill = agent ? 'rgba(255,255,255,.85)' : '#5f6880'
    return (
      <g>
        <rect x={x} y={y} width={w} height={h} rx={12} fill={fill} stroke={stroke} strokeWidth={agent ? 0 : 1.6}
          strokeDasharray={kind === 'code' ? '5 4' : undefined} />
        {agent && (
          <g>
            <rect x={x + w - 64} y={y - 9} width={58} height={18} rx={9} fill="#ffffff" stroke={color} strokeWidth={1.5} />
            <text x={x + w - 35} y={y + 4} textAnchor="middle" className="d-badge" fill={color}>✦ AI agent</text>
          </g>
        )}
        <text x={x + w / 2} y={y + h / 2 - 3} textAnchor="middle" className="d-title" fill={titleFill}>{title}</text>
        <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" className="d-sub" fill={subFill}>{sub}</text>
      </g>
    )
  }
  // A right-angled arrow through the given points, with an optional label chip at (lx, ly).
  const route = (pts: [number, number][], label?: string, lx?: number, ly?: number, color = INK) => {
    const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' ')
    const w = label ? label.length * 5.6 + 14 : 0
    return (
      <g>
        <path d={d} fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round" markerEnd="url(#ah)" />
        {label && lx !== undefined && ly !== undefined && (
          <g>
            <rect x={lx - w / 2} y={ly - 10} width={w} height={18} rx={9} fill="#ffffff" stroke="#e3e7ee" />
            <text x={lx} y={ly + 3} textAnchor="middle" className="d-edge">{label}</text>
          </g>
        )}
      </g>
    )
  }
  const lane = (y: number, h: number, n: string, label: string) => (
    <g>
      <rect x={0} y={y} width={1000} height={h} rx={14} fill="#f7f8fb" />
      <text x={16} y={y + 22} className="d-lane">{n} · {label}</text>
    </g>
  )
  return (
    <svg viewBox="0 0 1000 560" className="diagram" role="img"
      aria-label="How Bookend's five AI agents hand off: code decides who runs next">
      <defs>
        <marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0L10 5L0 10z" fill={INK} />
        </marker>
      </defs>

      {/* legend */}
      <g transform="translate(560, 0)">
        <rect x={0} y={2} width={22} height={14} rx={4} fill={AGENTS.moderator.color} />
        <text x={28} y={13} className="d-legend">AI agent (gpt-6-luna)</text>
        <rect x={160} y={2} width={22} height={14} rx={4} fill="#fff" stroke="#9aa3b5" strokeDasharray="4 3" strokeWidth={1.4} />
        <text x={188} y={13} className="d-legend">Code, no AI</text>
        <rect x={278} y={2} width={22} height={14} rx={4} fill="#eef6f8" stroke="#3f7484" strokeWidth={1.4} />
        <text x={306} y={13} className="d-legend">People</text>
      </g>

      {/* Lane 1: a reader finishes a book */}
      {lane(30, 190, '1', 'A READER FINISHES A BOOK')}
      {node(20, 100, 140, 56, 'people', 'Reader', 'logs a finished book')}
      {node(205, 100, 165, 56, 'code', 'Match query', 'same book, same window')}
      {node(440, 136, 185, 62, 'agent', 'Matchmaker', 'only if nobody found', AGENTS.matchmaker.color)}
      {node(715, 52, 255, 56, 'people', 'Readers room', 'real people (Host optional)')}
      {node(715, 140, 255, 62, 'agent', 'Booksy', 'AI reading companion, 1-on-1', AGENTS.companion.color)}
      {route([[160, 128], [203, 128]])}
      {route([[288, 100], [288, 80], [713, 80]], 'readers found', 500, 80)}
      {route([[370, 145], [405, 145], [405, 167], [438, 167]], 'nobody', 405, 145)}
      {route([[625, 154], [665, 154], [665, 96], [713, 96]], 'wider window', 665, 122)}
      {route([[625, 180], [713, 180]], 'no one nearby', 669, 180)}

      {/* Lane 2: every chat message */}
      {lane(232, 170, '2', 'EVERY CHAT MESSAGE')}
      {node(20, 280, 140, 56, 'people', 'Message', 'from a reader')}
      {node(205, 280, 165, 56, 'code', 'Code screen', 'contact info, links, tricks')}
      {node(440, 274, 185, 62, 'agent', 'Moderator', 'judges everything else', AGENTS.moderator.color)}
      {node(715, 280, 120, 56, 'people', 'Posted', 'in the room')}
      {node(860, 274, 120, 62, 'agent', 'Host', 'if on', AGENTS.host.color)}
      {node(440, 356, 185, 36, 'blocked', 'Hidden', '')}
      {route([[160, 308], [203, 308]])}
      {route([[370, 308], [438, 308]], 'passes', 404, 308)}
      {route([[625, 308], [713, 308]], 'allowed', 669, 308)}
      {route([[835, 308], [858, 308]])}
      {route([[288, 336], [288, 374], [438, 374]], 'caught', 340, 374, '#a8321e')}
      {route([[532, 336], [532, 354]], undefined, undefined, undefined, '#a8321e')}
      <text x={640} y={378} className="d-sub" fill="#a8321e">only the sender sees it, with the reason</text>

      {/* Lane 3: your next book */}
      {lane(414, 140, '3', 'YOUR NEXT BOOK')}
      {node(20, 462, 140, 56, 'people', 'Reader', 'asks, or logs a book')}
      {node(205, 456, 185, 62, 'agent', 'Recommendation', 'reads shelf, searches', AGENTS.recommender.color)}
      {node(465, 462, 160, 56, 'code', 'Open Library', 'real catalog search')}
      {node(715, 462, 255, 56, 'code', 'Picks check', 'must be search results')}
      {route([[160, 490], [203, 490]])}
      {route([[390, 478], [463, 478]], 'search', 426, 478)}
      {route([[463, 500], [390, 500]], 'results', 426, 500)}
      {route([[625, 490], [713, 490]], 'picks', 669, 490)}
    </svg>
  )
}
