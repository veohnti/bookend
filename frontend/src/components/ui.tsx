import { useState } from 'react'
import { AGENTS, type Book } from '../api'

export function Cover({ book, size = 'md' }: { book: Pick<Book, 'title' | 'cover_url'>; size?: 'xs' | 'sm' | 'md' | 'lg' }) {
  const [broken, setBroken] = useState(false)
  if (!book.cover_url || broken) {
    return (
      <div className={`cover ${size} placeholder`}>
        <span>{book.title}</span>
      </div>
    )
  }
  return <img className={`cover ${size}`} src={book.cover_url} alt={`Cover of ${book.title}`} onError={() => setBroken(true)} />
}

export function Stars({ n, onChange }: { n: number | null; onChange?: (n: number) => void }) {
  return (
    <span className={onChange ? 'stars editable' : 'stars'}>
      {[1, 2, 3, 4, 5].map((i) =>
        onChange ? (
          <button key={i} type="button" className={n && i <= n ? 'on' : ''} onClick={() => onChange(i)} aria-label={`${i} stars`}>
            ★
          </button>
        ) : (
          <span key={i} className={n && i <= n ? 'on' : ''}>
            ★
          </span>
        ),
      )}
    </span>
  )
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

export function AgentTag({ agent, suffix }: { agent: string; suffix?: string }) {
  const a = AGENTS[agent]
  return (
    <span className="agent-tag" style={{ background: a?.color ?? '#555' }}>
      {a?.label ?? agent} · AI{suffix ? ` · ${suffix}` : ''}
    </span>
  )
}

export function Dots() {
  return (
    <span className="dots">
      <i />
      <i />
      <i />
    </span>
  )
}
