import { useState, useEffect } from 'react'
import TicketsList from './components/TicketsList'
import NewTicketModal from './components/NewTicketModal'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    fetch('/api/me')
      .then(r => {
        if (r.status === 401) { window.location.href = '/login'; return null }
        return r.json()
      })
      .then(data => { if (data && !data.error) setUser(data) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      Chargement…
    </div>
  )

  if (!user) return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-icon">🎫</div>
        <div className="login-title">Tickets App</div>
        <div className="login-subtitle">Connectez-vous pour accéder à vos tickets</div>
        <a href="/login">
          <button className="btn-primary" style={{ width: '100%', padding: '12px' }}>
            🔐 Connexion via Keycloak
          </button>
        </a>
      </div>
    </div>
  )

  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">🎫 Tickets</div>
        <div className="navbar-right">
          <div className="user-chip">
            👤 {user.username}
            {user.roles?.map(r => (
              <span key={r} className="role-badge">{r}</span>
            ))}
          </div>
          <a href="/logout">
            <button className="btn-ghost" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
              Déconnexion
            </button>
          </a>
        </div>
      </nav>

      <div className="container">
        <div className="page-header">
          <div className="page-title">Mes Tickets</div>
          <button className="btn-primary" onClick={() => setShowNew(true)}>
            + Nouveau Ticket
          </button>
        </div>

        <TicketsList key={refresh} />
      </div>

      {showNew && (
        <NewTicketModal
          onClose={() => setShowNew(false)}
          onCreated={() => { setShowNew(false); setRefresh(r => r + 1) }}
        />
      )}
    </>
  )
}
