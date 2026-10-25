import { useEffect, useState } from 'react'
import { api, session, whenSignedOut, type User } from './api'
import Shelf from './components/Shelf'
import Chats from './components/Chats'
import Discover from './components/Discover'
import Behind from './components/Behind'
import BookendLogo from './components/BookendLogo'
import AuthScreen from './components/AuthScreen'

type Tab = 'shelf' | 'chats' | 'discover' | 'behind'

const TABS: { id: Tab; label: string }[] = [
  { id: 'shelf', label: 'Home' },
  { id: 'chats', label: "Let's chat about it" },
  { id: 'discover', label: 'Your Next Book' },
  { id: 'behind', label: 'Behind the scenes' },
]

export default function App() {
  const [me, setMe] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [tab, setTab] = useState<Tab>('shelf')
  const [openRoom, setOpenRoom] = useState<number | null>(null)
  const [health, setHealth] = useState<{ has_api_key: boolean } | null>(null)

  useEffect(() => {
    whenSignedOut(() => {
      session.clear()
      setMe(null)
    })
    api.health().then(setHealth).catch(() => setHealth({ has_api_key: false }))
    if (!session.get()) return setChecking(false)
    api.me().then(setMe).catch(() => session.clear()).finally(() => setChecking(false))
  }, [])

  const signedIn = (u: User) => {
    setMe(u)
    setTab('shelf')
    setOpenRoom(null)
  }

  const logOut = async () => {
    await api.logout().catch(() => {})
    session.clear()
    setMe(null)
  }

  const goToRoom = (roomId: number) => {
    setOpenRoom(roomId)
    setTab('chats')
  }

  if (checking) return <div className="app" />
  if (!me) return (
    <div className="app">
      <AuthScreen onSignedIn={signedIn} />
    </div>
  )
  const uid = me.id

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setTab('shelf')} aria-label="Bookend home">
          <BookendLogo compact />
        </button>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? 'tab active' : 'tab'} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="signed-in">
          <span className="avatar sm" style={{ background: me.color }}>
            {me.display_name[0]}
          </span>
          <span className="me-name">
            <b>{me.display_name}</b>
            {me.is_demo && <span className="demo-tag">Demo reader</span>}
          </span>
          <button className="btn ghost small-btn" onClick={logOut}>
            {me.is_demo ? 'Switch reader' : 'Log out'}
          </button>
        </div>
      </header>

      {health && !health.has_api_key && (
        <div className="banner warn">
          No <code>PORTKEY_API_KEY</code> found in <code>.env</code> (this folder or the one above). Reader chat
          works, but the AI agents are off.
        </div>
      )}

      <main className="main">
        {tab === 'shelf' && (
          <>
            <div className="masthead">
              <BookendLogo />
              <p className="tagline">
                Book club, <em>on your own time</em>, and without the books you just don't want to read.
              </p>
            </div>
            <Shelf uid={uid} onOpenRoom={goToRoom} onDiscover={() => setTab('discover')} />
          </>
        )}
        {tab === 'chats' && <Chats uid={uid} openRoom={openRoom} setOpenRoom={setOpenRoom} />}
        {tab === 'discover' && <Discover uid={uid} onOpenRoom={goToRoom} />}
        {tab === 'behind' && <Behind />}
      </main>
      <footer className="foot">
        Demo readers are sample data · Books from Open Library · AI by gpt-6-luna · Tip: open a second browser tab and pick
        another demo reader to chat with yourself
      </footer>
    </div>
  )
}
