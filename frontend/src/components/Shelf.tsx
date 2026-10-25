import { useEffect, useRef, useState } from 'react'
import { api, daysAgoLabel, type Book, type MatchResult, type Pick, type RoomSummary, type ShelfItem } from '../api'
import { AgentTag, Cover, Spinner, Stars } from './ui'
import Booksy from './Booksy'

const WINDOWS = [7, 30, 90, 365]

type Last = (Book & { reader_counts: Record<string, number>; recent_readers?: { display_name: string; color: string; days_ago: number }[]; room_id: number | null; is_member?: boolean }) | null
type Next = { based_on: ShelfItem | null; status: 'empty' | 'pending' | 'ready'; picks: Pick[]; message?: string }

export default function Shelf({ uid, onOpenRoom, onDiscover }: { uid: number; onOpenRoom: (id: number) => void; onDiscover: () => void }) {
  const [shelf, setShelf] = useState<ShelfItem[]>([])
  const [covers, setCovers] = useState<Book[]>([])
  const [last, setLast] = useState<Last>(null)
  const [next, setNext] = useState<Next | null>(null)
  const [myRooms, setMyRooms] = useState<RoomSummary[]>([])
  const [logging, setLogging] = useState(false)
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Book[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [selected, setSelected] = useState<Book | null>(null)
  const [busy, setBusy] = useState(false)
  const [suggest, setSuggest] = useState<Book[]>([])
  const [suggesting, setSuggesting] = useState(false)
  const flowRef = useRef<HTMLDivElement>(null)
  const typed = useRef(0)

  // Suggestions while typing: wait for a short pause, and ignore answers to older keystrokes.
  useEffect(() => {
    const text = q.trim()
    const n = ++typed.current
    if (text.length < 2 || selected) {
      setSuggest([])
      setSuggesting(false)
      return
    }
    setSuggesting(true)
    const t = setTimeout(async () => {
      try {
        const hits = await api.search(text, true)
        if (n === typed.current) setSuggest(hits)
      } finally {
        if (n === typed.current) setSuggesting(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [q, selected])

  const load = async () => {
    const sh = await api.shelf(uid)
    setShelf(sh)
    const latest = [...sh].sort((a, b) => b.finished_on.localeCompare(a.finished_on))[0]
    setLast(latest ? await api.book(latest.work_id, uid) : null)
    setNext(await api.next(uid))
    setMyRooms((await api.rooms(uid)).filter((r) => r.kind === 'readers'))
  }

  useEffect(() => {
    load()
    api.covers().then(setCovers)
    setSelected(null)
    setResults(null)
    setLogging(false)
  }, [uid])

  // "Your next book" is written by the Recommendation agent in the background; check back until it's ready.
  useEffect(() => {
    if (next?.status !== 'pending') return
    const t = setInterval(() => api.next(uid).then(setNext), 3000)
    return () => clearInterval(t)
  }, [next?.status, uid])

  const pick = (b: Book) => {
    setSelected(b)
    setLogging(true)
    setTimeout(() => flowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const doSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!q.trim()) return
    setSearching(true)
    setSuggest([])
    typed.current++
    try {
      setResults(await api.search(q))
    } finally {
      setSearching(false)
    }
  }

  const joinReaders = async () => {
    if (!last) return
    setBusy(true)
    try {
      const { room_id } = await api.joinReaders(uid, last.work_id, true)
      onOpenRoom(room_id)
    } finally {
      setBusy(false)
    }
  }

  const talkToCompanion = async () => {
    if (!last) return
    setBusy(true)
    try {
      const { room_id } = await api.companionRoom(uid, last.work_id)
      onOpenRoom(room_id)
    } finally {
      setBusy(false)
    }
  }

  const readers30 = last?.reader_counts?.['30'] ?? 0
  const readers365 = last?.reader_counts?.['365'] ?? 0

  return (
    <div className="home">
      <div className="home-main">
        {/* Log a book */}
        <section className="log" ref={flowRef}>
          {!logging ? (
            <button className="log-btn" onClick={() => setLogging(true)}>
              Log a book <span className="arrow">→</span>
            </button>
          ) : (
            <div className="card log-card">
              <h2>
                Just turned the <em>last page?</em>
              </h2>
              <form className="search" onSubmit={doSearch}>
                <div className="typeahead">
                  <input autoFocus value={q} placeholder="Start typing a title or author…"
                    onChange={(e) => { setQ(e.target.value); setResults(null); setSelected(null) }}
                    onKeyDown={(e) => e.key === 'Escape' && setSuggest([])} />
                  {suggesting && <span className="ta-spin"><Spinner /></span>}
                  {suggest.length > 0 && (
                    <ul className="suggestions" role="listbox">
                      {suggest.map((b) => (
                        <li key={b.work_id}>
                          <button type="button" onClick={() => { setSelected(b); setSuggest([]); setQ(b.title) }}>
                            <Cover book={b} size="xs" />
                            <span>
                              <span className="r-title">{b.title}</span>
                              <span className="muted small">
                                {b.author}
                                {b.first_publish_year ? ` · ${b.first_publish_year}` : ''}
                              </span>
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <button className="btn primary" disabled={searching}>
                  {searching ? <Spinner /> : 'Search'}
                </button>
                <button type="button" className="btn ghost" onClick={() => { setLogging(false); setSelected(null); setResults(null) }}>
                  Close
                </button>
              </form>
              {results && !selected && (
                <div className="results">
                  {results.length === 0 && <p className="muted">No books found. Try another spelling.</p>}
                  {results.map((b) => (
                    <button key={b.work_id} className="result" onClick={() => setSelected(b)}>
                      <Cover book={b} size="sm" />
                      <div>
                        <div className="r-title">{b.title}</div>
                        <div className="muted small">
                          {b.author}
                          {b.first_publish_year ? ` · ${b.first_publish_year}` : ''}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {selected && (
                <FinishFlow
                  key={selected.work_id + uid}
                  uid={uid}
                  book={selected}
                  alreadyFinished={shelf.find((s) => s.work_id === selected.work_id)}
                  onClose={() => setSelected(null)}
                  onFinished={load}
                  onOpenRoom={onOpenRoom}
                />
              )}
            </div>
          )}
        </section>

        {/* Ways to talk about it: people, Booksy (AI), and the reader rooms you've already joined */}
        <section className="talk-cards">
          <div className="talk-card people">
            <div className="eyebrow">With people</div>
            {last && readers30 > 0 && (
              <div className="avatar-stack">
                {(last.recent_readers ?? []).map((r, i) => (
                  <span key={i} className="avatar" style={{ background: r.color }} title={`${r.display_name}, ${daysAgoLabel(r.days_ago)}`}>
                    {r.display_name[0]}
                  </span>
                ))}
              </div>
            )}
            {last ? (
              readers30 > 0 ? (
                <>
                  <h3>
                    {readers30} {readers30 === 1 ? 'reader' : 'readers'} just finished <i>{last.title}</i>
                  </h3>
                  <p className="muted small">Real people, anywhere in the world. Spoilers welcome: everyone in the room has finished it.</p>
                  {last.is_member && last.room_id ? (
                    <button className="btn primary" onClick={() => onOpenRoom(last.room_id!)}>
                      Open your room
                    </button>
                  ) : (
                    <button className="btn primary" disabled={busy} onClick={joinReaders}>
                      Join them
                    </button>
                  )}
                </>
              ) : (
                <>
                  <h3>
                    Nobody else finished <i>{last.title}</i> this month{readers365 ? `, but ${readers365} did this year` : ' yet'}
                  </h3>
                  <p className="muted small">Try a wider window and our Matchmaker will look further.</p>
                  {last.is_member && last.room_id ? (
                    <button className="btn primary" onClick={() => onOpenRoom(last.room_id!)}>
                      Open your room
                    </button>
                  ) : (
                    <button className="btn primary" onClick={() => pick(last)}>
                      Find readers
                    </button>
                  )}
                </>
              )
            ) : (
              <>
                <h3>Meet people who just finished your book</h3>
                <p className="muted small">Log a book and we'll find readers who finished it around the same time.</p>
              </>
            )}
          </div>

          <div className="talk-card ai">
            <Booksy size={96} className="card-booksy" />
            <div className="eyebrow">With us · AI</div>
            <h3>Talk with Booksy, your AI reading companion</h3>
            <p className="muted small">
              {last ? <>Talk about <i>{last.title}</i> right now. </> : null}
              Booksy knows the book's catalog record and says when it isn't sure.
            </p>
            <div className="btn-row">
              <button className="btn coral" disabled={busy || !last} onClick={talkToCompanion}>
                Talk with Booksy
              </button>
              <button className="btn ghost" onClick={onDiscover}>
                Find your next book
              </button>
            </div>
          </div>

          <div className="talk-card rooms">
            <div className="eyebrow">Your rooms</div>
            {myRooms.length === 0 ? (
              <>
                <h3>No rooms yet</h3>
                <p className="muted small">Reader rooms you join show up here, one click away.</p>
              </>
            ) : (
              <>
                <h3>Pick up where you left off</h3>
                <div className="room-links">
                  {myRooms.slice(0, 4).map((r) => (
                    <button key={r.id} className="room-link" onClick={() => onOpenRoom(r.id)}>
                      <Cover book={{ title: r.title ?? '', cover_url: r.cover_url }} size="xs" />
                      <span className="rl-body">
                        <span className="r-title">{r.title}</span>
                        <span className="muted tiny ellipsis">
                          {r.members} {r.members === 1 ? 'reader' : 'readers'}
                          {r.last_text ? ` · ${r.last_text.replace(/\*/g, '')}` : ''}
                        </span>
                      </span>
                      <span className="rl-arrow">→</span>
                    </button>
                  ))}
                </div>
                {myRooms.length > 4 && <p className="muted tiny">And {myRooms.length - 4} more in Let's chat about it.</p>}
              </>
            )}
          </div>
        </section>

        {/* Your next book */}
        <section className="next-book">
          <h2 className="hand">
            Your <em>next</em> book
          </h2>
          {next?.based_on && (
            <p className="muted small">
              Because you just finished <i>{next.based_on.title}</i>. Every pick comes from a real catalog search.
              <AgentTag agent="recommender" />
            </p>
          )}
          {next?.status === 'empty' && <p className="muted">Log a book to get suggestions.</p>}
          {next?.status === 'pending' && (
            <div className="next-grid">
              {[0, 1, 2].map((i) => (
                <div key={i} className="next-card loading">
                  <div className="cover md placeholder shimmer" />
                  <div className="muted small">
                    <Spinner /> Reading your shelf…
                  </div>
                </div>
              ))}
            </div>
          )}
          {next?.status === 'ready' && (
            <div className="next-grid">
              {next.picks.map((p) => (
                <button key={p.work_id} className="next-card" onClick={() => pick(p)}>
                  <Cover book={p} size="md" />
                  <div className="r-title">{p.title}</div>
                  <div className="muted small">{p.author}</div>
                  <div className="why">{p.why}</div>
                  {p.active_readers > 0 && (
                    <span className="pill green">
                      {p.active_readers} reader{p.active_readers === 1 ? '' : 's'} discussing now
                    </span>
                  )}
                </button>
              ))}
              {next.picks.length === 0 && <p className="muted">{next.message || 'No picks this time.'}</p>}
            </div>
          )}
        </section>

        {/* Your shelf */}
        <section className="my-shelf">
          <h2>Your shelf</h2>
          {shelf.length === 0 && <p className="muted">Nothing here yet.</p>}
          <div className="wood-shelf">
            {shelf.map((s) => (
              <button key={s.work_id} className="shelf-book" onClick={() => pick(s)} title={`${s.title}, finished ${s.finished_on}`}>
                <Cover book={s} size="md" />
                <Stars n={s.rating} />
              </button>
            ))}
          </div>
          <div className="plank" />
        </section>
      </div>

      {/* Scrolling covers */}
      <aside className="cover-rail" aria-label="Books on Bookend">
        <div className="rail-track" style={{ animationDuration: `${Math.max(covers.length, 6) * 4}s` }}>
          {[...covers, ...covers].map((b, i) => (
            <button key={i} className="rail-book" onClick={() => pick(b)} title={`${b.title} by ${b.author}`}>
              <Cover book={b} size="md" />
            </button>
          ))}
        </div>
      </aside>
    </div>
  )
}

export function FinishFlow({
  uid,
  book,
  alreadyFinished,
  onClose,
  onFinished,
  onOpenRoom,
}: {
  uid: number
  book: Book
  alreadyFinished?: ShelfItem
  onClose: () => void
  onFinished: () => void
  onOpenRoom: (id: number) => void
}) {
  const today = new Date().toISOString().slice(0, 10)
  const [date, setDate] = useState(alreadyFinished?.finished_on ?? today)
  const [rating, setRating] = useState<number | null>(alreadyFinished?.rating ?? null)
  const [windowDays, setWindowDays] = useState(30)
  const [stage, setStage] = useState<'form' | 'matching' | 'matched'>('form')
  const [match, setMatch] = useState<MatchResult | null>(null)
  const [hostOn, setHostOn] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const go = async () => {
    setError(null)
    setStage('matching')
    try {
      await api.finish(uid, book, date, rating)
      onFinished()
      setMatch(await api.match(uid, book.work_id, windowDays))
      setStage('matched')
    } catch (e: any) {
      setError(e.message)
      setStage('form')
    }
  }

  const join = async (workId: string) => {
    setBusy(true)
    try {
      const { room_id } = await api.joinReaders(uid, workId, hostOn)
      onOpenRoom(room_id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const companion = async () => {
    setBusy(true)
    try {
      const { room_id } = await api.companionRoom(uid, book.work_id)
      onOpenRoom(room_id)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card finish">
      <button className="close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="finish-head">
        <Cover book={book} size="lg" />
        <div>
          <h2>{book.title}</h2>
          <div className="muted">
            {book.author}
            {book.first_publish_year ? ` · ${book.first_publish_year}` : ''}
          </div>
          {stage === 'form' && (
            <div className="finish-form">
              <label>
                Finished on
                <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
              </label>
              <label>
                Your rating
                <Stars n={rating} onChange={setRating} />
              </label>
              <label>
                Match me with readers who finished in the last
                <div className="seg">
                  {WINDOWS.map((w) => (
                    <button key={w} className={w === windowDays ? 'on' : ''} onClick={() => setWindowDays(w)}>
                      {w === 365 ? 'year' : `${w} days`}
                    </button>
                  ))}
                </div>
              </label>
              <button className="btn primary big" onClick={go}>
                {alreadyFinished ? 'Find readers' : 'Mark finished & find readers'}
              </button>
            </div>
          )}
          {stage === 'matching' && (
            <p className="muted matching">
              <Spinner /> Looking for readers who finished it in the last {windowDays} days…
            </p>
          )}
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}

      {stage === 'matched' && match && (
        <div className="match">
          <div className="match-msg">
            {match.agent_ran && <AgentTag agent="matchmaker" />}
            <p>{match.message}</p>
          </div>
          {match.readers && match.readers.length > 0 && (
            <div className="readers">
              {match.readers.map((r, i) => (
                <div key={i} className="reader-chip">
                  <span className="avatar sm" style={{ background: r.color }}>
                    {r.display_name[0]}
                  </span>
                  {r.display_name} <span className="muted tiny">{daysAgoLabel(r.days_ago)}</span>
                </div>
              ))}
            </div>
          )}
          <h3 className="want">Want to talk about it?</h3>
          <div className="choices">
            {(match.action === 'join_readers' || match.action === 'widen_window') && (
              <div className="choice readers-choice">
                <h4>Chat with readers</h4>
                <p className="muted small">
                  {match.room_id ? 'Join the room for this book.' : 'Open the room for this book.'} Safety moderation is
                  always on.
                </p>
                <label className="toggle">
                  <input type="checkbox" checked={hostOn} onChange={(e) => setHostOn(e.target.checked)} />
                  <span>Add a Discussion Host (AI) to get the conversation going</span>
                </label>
                <button className="btn primary" disabled={busy} onClick={() => join(book.work_id)}>
                  Join the readers
                </button>
              </div>
            )}
            {match.action === 'related_book' && match.related_book && (
              <div className="choice readers-choice">
                <h4>Try a related book</h4>
                <div className="related">
                  <Cover book={match.related_book} size="sm" />
                  <div>
                    <div className="r-title">{match.related_book.title}</div>
                    <div className="muted small">
                      {match.related_book.author} · {match.related_readers} recent reader
                      {match.related_readers === 1 ? '' : 's'}
                    </div>
                  </div>
                </div>
                <p className="muted small">Finish it to join that room, or talk about this one with Booksy now.</p>
              </div>
            )}
            <div className="choice companion-choice">
              <h4><Booksy size={34} /> Talk with Booksy</h4>
              <p className="muted small">
                Your AI reading companion, grounded in the book's catalog record. Booksy says when it isn't sure.
              </p>
              <button className="btn plum" disabled={busy} onClick={companion}>
                Talk with Booksy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
