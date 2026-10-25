import { useEffect, useRef, useState } from 'react'
import { AGENTS, api, daysAgoLabel, type Message, type RoomState, type RoomSummary } from '../api'
import { AgentTag, Cover, Dots } from './ui'
import { PickCard } from './Discover'
import Globe from './Globe'
import Booksy from './Booksy'

const KIND_LABEL = { readers: 'Readers', companion: 'Booksy', recs: 'Your Next Book' }

export default function Chats({
  uid,
  openRoom,
  setOpenRoom,
}: {
  uid: number
  openRoom: number | null
  setOpenRoom: (id: number | null) => void
}) {
  const [rooms, setRooms] = useState<RoomSummary[]>([])

  useEffect(() => {
    const load = () => api.rooms(uid).then(setRooms)
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [uid])

  useEffect(() => {
    if (openRoom === null && rooms.length) setOpenRoom(rooms[0].id)
  }, [rooms, openRoom])

  const people = rooms.filter((r) => r.kind === 'readers')
  const ai = rooms.filter((r) => r.kind !== 'readers')

  const item = (r: RoomSummary) => (
    <button key={r.id} className={`room-item ${r.kind} ${r.id === openRoom ? 'on' : ''}`} onClick={() => setOpenRoom(r.id)}>
      {r.kind === 'recs' ? (
        <div className="cover xs placeholder recs-icon">✦</div>
      ) : (
        <Cover book={{ title: r.title ?? '', cover_url: r.cover_url }} size="xs" />
      )}
      <div className="ri-body">
        <span className="r-title">{r.kind === 'recs' ? 'Your Next Book' : r.title}</span>
        <span className={`kind ${r.kind}`}>
          {KIND_LABEL[r.kind]}
          {r.kind === 'readers' ? ` · ${r.members} ${r.members === 1 ? 'person' : 'people'}` : ' · AI'}
        </span>
        <div className="muted tiny ellipsis">{r.last_text?.replace(/\*/g, '')}</div>
      </div>
    </button>
  )

  return (
    <div className="chats-layout">
      <div className="chats-side">
        <aside className="card room-list">
          <h3>Your chats</h3>
          {rooms.length === 0 && <p className="muted small">No chats yet. Mark a book finished on your shelf to start one.</p>}
          {people.length > 0 && (
            <div className="room-group people">
              <div className="group-label">
                <span className="group-icon">👥</span> With readers <span className="group-sub">real people</span>
              </div>
              {people.map(item)}
            </div>
          )}
          {ai.length > 0 && (
            <div className="room-group ai">
              <div className="group-label">
                <Booksy size={22} /> With us <span className="group-sub">AI, not a person</span>
              </div>
              {ai.map(item)}
            </div>
          )}
        </aside>
        <div className="card globe-card">
          <Globe size={220} />
          <p className="small">
            Every reader room is people who finished the same book around the same time, <b>from anywhere in the world</b>.
          </p>
        </div>
      </div>
      {openRoom ? <ChatRoom key={`${openRoom}-${uid}`} uid={uid} roomId={openRoom} /> : <div className="card empty">Pick a chat.</div>}
    </div>
  )
}

export function ChatRoom({ uid, roomId }: { uid: number; roomId: number }) {
  const [state, setState] = useState<RoomState | null>(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [waitingAI, setWaitingAI] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  // The message being checked by the Moderator, shown faded until the saved copy arrives (never both at once).
  const [pending, setPending] = useState<{ text: string; afterId: number } | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const lastCount = useRef(0)

  const load = () => api.room(roomId, uid).then(setState).catch(() => {})

  useEffect(() => {
    load()
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [roomId, uid])

  useEffect(() => {
    const n = state?.messages.length ?? 0
    if (n !== lastCount.current) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    lastCount.current = n
  }, [state?.messages.length, waitingAI, state?.host_typing])

  if (!state) return <div className="card empty">Loading…</div>
  const { room, messages, members } = state

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault()
    const t = text.trim()
    if (!t || sending) return
    setSending(true)
    setNotice(null)
    setText('')
    setPending({ text: t, afterId: messages.length ? messages[messages.length - 1].id : 0 })
    const aiReplies = room.kind !== 'readers'
    if (aiReplies) setWaitingAI(true)
    try {
      const out = await api.send(roomId, uid, t)
      await load()
      if (out.verdict?.verdict === 'hide') {
        setWaitingAI(false)
        if (out.verdict.muted_until) setNotice('You have been muted for an hour after several hidden messages.')
      }
    } catch (err: any) {
      setNotice(err.message)
      setText(t)
    } finally {
      setSending(false)
      setWaitingAI(false)
      await load()
      setPending(null)
    }
  }

  const toggleHost = async () => {
    await api.toggleHost(roomId, uid, !room.host_on)
    load()
  }

  const title = room.kind === 'recs' ? 'Your Next Book' : room.title
  const placeholder =
    room.kind === 'readers'
      ? room.host_on
        ? 'Say something… (mention @host to ask the Discussion Host)'
        : 'Say something…'
      : room.kind === 'companion'
        ? 'Tell Booksy what you thought…'
        : 'e.g. "I loved Circe. Something mythic but modern?"'

  return (
    <section className={`card chat ${room.kind}`}>
      <header className="chat-head">
        {room.kind !== 'recs' && <Cover book={{ title: room.title ?? '', cover_url: room.cover_url }} size="sm" />}
        <div className="ch-main">
          <h2>{title}</h2>
          {room.author && <div className="muted small">{room.author}</div>}
          <div className="members">
            {room.kind === 'readers' &&
              members.map((m) => (
                <span key={m.id} className="member" title={daysAgoLabel(m.days_ago)}>
                  <span className="avatar xs" style={{ background: m.color }}>
                    {m.display_name[0]}
                  </span>
                  {m.id === uid ? 'You' : m.display_name}
                  {m.days_ago !== null && <span className="muted tiny"> · {m.days_ago}d</span>}
                </span>
              ))}
            {room.kind === 'companion' && <AgentTag agent="companion" />}
            {room.kind === 'recs' && <AgentTag agent="recommender" />}
          </div>
        </div>
        {room.kind === 'readers' && (
          <label className="toggle host-toggle">
            <input type="checkbox" checked={!!room.host_on} onChange={toggleHost} />
            <span>Discussion Host</span>
          </label>
        )}
        <span className="shield" title="Every message is checked by the Moderator before anyone sees it">
          🛡 Moderated
        </span>
      </header>
      {room.kind === 'readers' ? (
        <div className="who-banner people">
          <span className="wb-icon">👥</span>
          <div>
            <b>You're talking with real readers.</b>{' '}
            {(() => {
              const here = members.filter((m) => m.id !== uid).length
              const recent = state.recent_readers
              if (here > 0) return `${here} other ${here === 1 ? 'person' : 'people'} who finished this book ${here === 1 ? 'is' : 'are'} in this room.`
              return recent > 0
                ? `You're the first one here. ${recent} other ${recent === 1 ? 'reader' : 'readers'} finished it in the last 30 days and will see this room.`
                : "You're the first one here. Readers who finish it next will find this room."
            })()}
            {room.host_on ? ' The Discussion Host (AI) joins in now and then; its messages are labeled.' : ''}
          </div>
        </div>
      ) : (
        <div className="who-banner ai">
          <Booksy size={40} />
          <div>
            {room.kind === 'companion' ? (
              <>
                <b>You're talking with Booksy, your AI reading companion, not a person.</b> Booksy knows the book's
                catalog record and says when it isn't sure.
              </>
            ) : (
              <>
                <b>You're talking with us, an AI, not a person.</b> Every suggestion is a real book from the catalog.
              </>
            )}
          </div>
        </div>
      )}

      <div className="messages">
        {messages.map((m) => (
          <Bubble key={m.id} m={m} uid={uid} />
        ))}
        {pending && !messages.some((m) => m.user_id === uid && m.id > pending.afterId && m.text === pending.text) && (
          <div className="row mine">
            <div className="bubble mine pending">
              <div>{pending.text}</div>
              <div className="time">🛡 Checking…</div>
            </div>
          </div>
        )}
        {(state.host_typing || waitingAI) && (
          <div className={`bubble ai typing ${room.kind === 'readers' ? 'host' : room.kind === 'companion' ? 'companion' : 'librarian'}`}>
            <AgentTag agent={room.kind === 'readers' ? 'host' : room.kind === 'companion' ? 'companion' : 'recommender'} />
            <Dots />
          </div>
        )}
        <div ref={endRef} />
      </div>

      {notice && <div className="banner error">{notice}</div>}
      {state.muted_until ? (
        <div className="banner warn">You're muted until {state.muted_until.slice(11, 16)} after several hidden messages.</div>
      ) : (
        <form className="composer" onSubmit={send}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} maxLength={800} />
          <button className="btn primary" disabled={sending || !text.trim()}>
            Send
          </button>
        </form>
      )}
    </section>
  )
}

function Bubble({ m, uid }: { m: Message; uid: number }) {
  if (m.sender === 'system') return <div className="system-line">{m.text}</div>
  const time = m.created_at.slice(11, 16)

  if (m.status === 'hidden') {
    return (
      <div className="bubble mine hidden-msg">
        <div className="hidden-label">
          <span className="agent-tag" style={{ background: '#b3261e' }}>
            Hidden by {m.meta?.mod_layer === 'code' ? 'safety filter' : 'Moderator · AI'}
          </span>
          <span className="tiny">Only you can see this</span>
        </div>
        <div className="struck">{m.text}</div>
        <div className="mod-reason">{m.mod_reason}</div>
        {m.meta?.self_harm_support && (
          <div className="support">
            If you're going through a hard time, you don't have to handle it alone. In the US, call or text 988 (Suicide &
            Crisis Lifeline) any time.
          </div>
        )}
      </div>
    )
  }

  if (m.sender === 'user') {
    const mine = m.user_id === uid
    return (
      <div className={mine ? 'row mine' : 'row'}>
        {!mine && (
          <span className="avatar sm" style={{ background: m.color ?? '#777' }}>
            {m.display_name?.[0]}
          </span>
        )}
        <div className={mine ? 'bubble mine' : 'bubble'}>
          {!mine && <div className="who">{m.display_name}</div>}
          <div>{m.text}</div>
          <div className="time">{time}</div>
        </div>
      </div>
    )
  }

  const agent = m.sender === 'host' ? 'host' : m.sender === 'companion' ? 'companion' : 'recommender'
  const basis = m.meta?.basis
  return (
    <div className="row ai-row">
    {agent === 'companion' ? (
      <Booksy size={38} className="msg-booksy" />
    ) : (
      <span className="avatar sm ai-avatar" style={{ background: AGENTS[agent].color }} title="AI">
        ✦
      </span>
    )}
    <div className={`bubble ai ${m.sender}`}>
      <div className="ai-head">
        <AgentTag agent={agent} />
        {basis && !m.meta?.greeting && (
          <span className={`basis ${basis}`}>
            {basis === 'catalog' ? 'From the catalog record' : basis === 'general_knowledge' ? 'General knowledge' : 'Not sure'}
          </span>
        )}
      </div>
      <div className="ai-text">{renderText(m.text)}</div>
      {m.meta?.picks?.length > 0 && (
        <div className="picks">
          {m.meta.picks.map((p: any) => (
            <PickCard key={p.work_id} p={p} />
          ))}
        </div>
      )}
      <div className="time">
        {time}
      </div>
    </div>
    </div>
  )
}

function renderText(t: string) {
  // **bold** and *italic* only; everything else is plain text (never HTML)
  return t.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <b key={i}>{part.slice(2, -2)}</b>
      : part.startsWith('*') && part.endsWith('*') && part.length > 2 ? <em key={i}>{part.slice(1, -1)}</em> : part,
  )
}
