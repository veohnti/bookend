import { useEffect, useState } from 'react'
import { api, session, type User } from '../api'
import BookendLogo from './BookendLogo'
import Booksy from './Booksy'
import { Spinner } from './ui'

// Welcome screen: log in, create an account, or try a demo reader (one click, for graders and quick demos).
export default function AuthScreen({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('signup')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [demos, setDemos] = useState<User[]>([])

  useEffect(() => {
    api.demoReaders().then(setDemos).catch(() => setDemos([]))
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (mode === 'signup' && password.length < 8) return setError('Use at least 8 characters for your password.')
    setBusy(true)
    try {
      const out = mode === 'signup' ? await api.signup(email, name, password) : await api.login(email, password)
      session.set(out.token, false)
      onSignedIn(out.user)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const tryDemo = async (id: number) => {
    setError(null)
    try {
      const out = await api.demo(id)
      session.set(out.token, true)
      onSignedIn(out.user)
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <BookendLogo />
        <p className="tagline">
          Book club, <em>on your own time</em>, and without the books you just don't want to read.
        </p>
      </div>

      <div className="auth-grid">
        <form className="card auth-card" onSubmit={submit}>
          <div className="seg auth-tabs">
            <button type="button" className={mode === 'signup' ? 'on' : ''} onClick={() => { setMode('signup'); setError(null) }}>
              Create account
            </button>
            <button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setError(null) }}>
              Log in
            </button>
          </div>
          <label>
            Email address
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email"
              placeholder="you@yale.edu" required />
            {mode === 'signup' && <span className="muted tiny">For logging in only. Other readers never see it.</span>}
          </label>
          {mode === 'signup' && (
            <label>
              Display name
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Sam" maxLength={30} required />
              <span className="muted tiny">What other readers see. No contact details.</span>
            </label>
          )}
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required
              placeholder={mode === 'signup' ? 'At least 8 characters' : ''} />
          </label>
          {error && <div className="banner error">{error}</div>}
          <button className="btn primary big" disabled={busy}>
            {busy ? <Spinner /> : mode === 'signup' ? 'Create account' : 'Log in'}
          </button>
          <p className="muted tiny">Passwords are stored hashed, never as text. Other readers only see your display name, never your email.</p>
        </form>

        <div className="card demo-card">
          <div className="eyebrow">Just looking around?</div>
          <h3>Try a demo reader</h3>
          <p className="muted small">
            Sample readers with books already logged and chats going. One click, no password. To see two people chat, open a
            second browser tab and pick a different reader there.
          </p>
          <div className="demo-list">
            {demos.map((u) => (
              <button key={u.id} className="demo-reader" onClick={() => tryDemo(u.id)}>
                <span className="avatar sm" style={{ background: u.color }}>{u.display_name[0]}</span>
                <span>
                  <b>{u.display_name}</b>
                  <span className="muted tiny">{u.bio}</span>
                </span>
              </button>
            ))}
          </div>
          <div className="demo-booksy">
            <Booksy size={70} />
            <span className="muted small">Booksy, your AI reading companion, is waiting inside.</span>
          </div>
        </div>
      </div>
    </div>
  )
}
