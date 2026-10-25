import { useEffect, useState } from 'react'
import { api, type Pick } from '../api'
import { ChatRoom } from './Chats'
import { Cover } from './ui'

export default function Discover({ uid }: { uid: number; onOpenRoom: (id: number) => void }) {
  const [roomId, setRoomId] = useState<number | null>(null)

  useEffect(() => {
    setRoomId(null)
    api.recsRoom(uid).then((r) => setRoomId(r.room_id))
  }, [uid])

  return (
    <div className="discover">
      <div className="discover-intro">
        <h1>
          Your <em>next</em> book
        </h1>
        <p className="muted">
          Chat with the Recommendation agent. It reads your shelf, searches the Open Library catalog, and only suggests books
          it actually found there. Books other readers are discussing right now get a green tag.
        </p>
      </div>
      {roomId && <ChatRoom key={`${roomId}-${uid}`} uid={uid} roomId={roomId} />}
    </div>
  )
}

export function PickCard({ p }: { p: Pick }) {
  return (
    <div className="pick">
      <Cover book={p} size="sm" />
      <div>
        <div className="r-title">{p.title}</div>
        <div className="muted small">
          {p.author}
          {p.first_publish_year ? ` · ${p.first_publish_year}` : ''}
        </div>
        <div className="why">{p.why}</div>
        {p.active_readers > 0 && (
          <span className="pill green">
            {p.active_readers} reader{p.active_readers === 1 ? '' : 's'} discussing now
          </span>
        )}
        <span className="pill catalog" title={`Open Library work ${p.work_id}`}>
          ✓ In the catalog
        </span>
      </div>
    </div>
  )
}
