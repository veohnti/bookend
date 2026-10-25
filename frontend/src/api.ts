// Thin client for the Bookend API (same origin in production, proxied to :8000 in dev).

export type User = { id: number; username: string; display_name: string; color: string; bio: string; is_demo: boolean }

export type Book = {
  work_id: string
  title: string
  author: string
  cover_url: string | null
  first_publish_year?: number | null
  subjects?: string[]
  description?: string
  source?: string
}

export type ShelfItem = Book & { finished_on: string; rating: number | null }

export type Reader = { display_name: string; color: string; days_ago: number }

export type MatchResult = {
  work_id: string
  window_days: number
  room_id: number | null
  action: 'join_readers' | 'widen_window' | 'related_book' | 'companion'
  agent_ran: boolean
  message: string
  readers?: Reader[]
  related_book?: Book
  related_readers?: number
  run_id?: string
}

export type Message = {
  id: number
  room_id: number
  sender: 'user' | 'host' | 'companion' | 'librarian' | 'system'
  user_id: number | null
  display_name: string | null
  color: string | null
  text: string
  status: 'shown' | 'hidden'
  mod_category: string | null
  mod_reason: string | null
  meta: Record<string, any>
  created_at: string
}

export type Room = {
  id: number
  kind: 'readers' | 'companion' | 'recs'
  work_id: string | null
  owner_id: number | null
  host_on: number
  title: string | null
  author: string | null
  cover_url: string | null
}

export type RoomSummary = Room & { members: number; last_id: number | null; last_text: string | null }

export type RoomState = {
  room: Room
  messages: Message[]
  members: { id: number; display_name: string; color: string; days_ago: number | null }[]
  host_typing: boolean
  recent_readers: number
  muted_until: string | null
}

export type Pick = Book & { why: string; active_readers: number }

// Session token. Real accounts: localStorage (stays signed in across tabs). Demo readers: sessionStorage, so each
// browser tab can be a different demo reader (open two tabs to chat with yourself as two readers).
const TOKEN = 'bookend-token'
export const session = {
  get: () => sessionStorage.getItem(TOKEN) || localStorage.getItem(TOKEN),
  set: (token: string, demo: boolean) => {
    sessionStorage.removeItem(TOKEN)
    if (demo) sessionStorage.setItem(TOKEN, token)
    else localStorage.setItem(TOKEN, token)
  },
  clear: () => {
    sessionStorage.removeItem(TOKEN)
    localStorage.removeItem(TOKEN)
  },
}

let onSignedOut: () => void = () => {}
export const whenSignedOut = (fn: () => void) => (onSignedOut = fn)

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = session.get()
  const r = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init?.headers || {}) },
  })
  if (r.status === 401 && !path.startsWith('/auth/')) onSignedOut()
  if (!r.ok) {
    let detail = r.statusText
    try {
      detail = (await r.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return r.json()
}

const post = <T,>(path: string, body: unknown) => req<T>(path, { method: 'POST', body: JSON.stringify(body) })

type AuthOut = { token: string; user: User }

export const api = {
  health: () => req<{ has_api_key: boolean; env_file: string | null }>('/health'),
  me: () => req<User>('/auth/me'),
  signup: (email: string, display_name: string, password: string) =>
    post<AuthOut>('/auth/signup', { email, display_name, password }),
  login: (email: string, password: string) => post<AuthOut>('/auth/login', { email, password }),
  demo: (user_id: number) => post<AuthOut>('/auth/demo', { user_id }),
  demoReaders: () => req<User[]>('/auth/demo-readers'),
  logout: () => post('/auth/logout', {}),
  shelf: (_uid?: number) => req<ShelfItem[]>('/me/shelf'),
  search: (q: string, prefix = false) => req<Book[]>(`/search?q=${encodeURIComponent(q)}${prefix ? '&prefix=true' : ''}`),
  book: (workId: string, _uid?: number) =>
    req<Book & { reader_counts: Record<string, number>; room_id: number | null; my_finish: any }>(`/books/${workId}`),
  next: (_uid?: number) => req<any>('/me/next'),
  covers: () => req<Book[]>('/covers'),
  activeBooks: () => req<(Book & { recent_finishers: number })[]>('/active-books'),
  finish: (_uid: number, book: Book, finished_on: string, rating: number | null) =>
    post<Book>('/finish', { book, finished_on, rating }),
  match: (_uid: number, work_id: string, window_days: number) => post<MatchResult>('/match', { work_id, window_days }),
  joinReaders: (_uid: number, work_id: string, host_on: boolean | null) =>
    post<{ room_id: number }>('/rooms/readers/join', { work_id, host_on }),
  companionRoom: (_uid: number, work_id: string) => post<{ room_id: number }>('/rooms/companion', { work_id }),
  recsRoom: (_uid: number) => post<{ room_id: number }>('/rooms/recs', {}),
  rooms: (_uid: number) => req<RoomSummary[]>('/me/rooms'),
  room: (rid: number, _uid: number) => req<RoomState>(`/rooms/${rid}`),
  send: (rid: number, _uid: number, text: string) =>
    post<{ message_id: number; verdict: any; reply?: any }>(`/rooms/${rid}/messages`, { text }),
  toggleHost: (rid: number, _uid: number, on: boolean) => post(`/rooms/${rid}/host`, { on }),
  activity: (limit = 40) => req<any[]>(`/activity?limit=${limit}`),
  usage: () => req<any>('/usage'),
  auditEvents: (limit = 40) => req<any[]>(`/audit-events?limit=${limit}`),
  moderation: () => req<any[]>('/moderation'),
  reset: () => post('/reset', {}),
}

export function daysAgoLabel(d: number | null | undefined) {
  if (d === null || d === undefined) return ''
  if (d === 0) return 'finished today'
  if (d === 1) return 'finished yesterday'
  return `finished ${d} days ago`
}

export const AGENTS: Record<string, { label: string; color: string; blurb: string }> = {
  moderator: { label: 'Moderator', color: '#a8321e', blurb: 'Checks every message before anyone sees it.' },
  matchmaker: { label: 'Matchmaker', color: '#3f7484', blurb: 'Finds a fallback when nobody finished in your window.' },
  host: { label: 'Discussion Host', color: '#bb7125', blurb: 'Optional. Welcomes, nudges, answers @host.' },
  companion: { label: 'Booksy', color: '#d9634a', blurb: 'Your AI reading companion, grounded in the catalog.' },
  recommender: { label: 'Recommendation', color: '#857a22', blurb: 'Suggests real books from catalog searches.' },
}
