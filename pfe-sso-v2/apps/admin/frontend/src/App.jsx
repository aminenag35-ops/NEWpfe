import { useState, useEffect } from 'react'
import UsersPanel from './components/UsersPanel'
import AuditPanel from './components/AuditPanel'
import AlertsPanel from './components/AlertsPanel'
import BlockedIPsPanel from './components/BlockedIPsPanel'

const TABS = [
  { id: 'users', label: '👥 Utilisateurs' },
  { id: 'alerts', label: '🚨 Alertes ML' },
  { id: 'blocked-ips', label: '🚫 IPs Bloquées' },
  { id: 'audit', label: '📋 Audit Log' },
]

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('users')

  useEffect(() => {
    fetch('/api/me')
      .then(r => {
        if (r.status === 401) { window.location.href = '/login'; return null }
        if (r.status === 403) { return null }
        return r.json()
      })
      .then(data => { if (data) setUser(data) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      Chargement…
    </div>
  )

  if (!user) return null

  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">🛡️ Admin Console</div>
        <div className="navbar-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="navbar-user">
          <span>{user.username}</span>
          <a href="/logout" style={{ color: 'var(--text-muted)' }}>Déconnexion</a>
        </div>
      </nav>

      <main className="main-content">
        {activeTab === 'users' && <UsersPanel />}
        {activeTab === 'alerts' && <AlertsPanel />}
        {activeTab === 'blocked-ips' && <BlockedIPsPanel />}
        {activeTab === 'audit' && <AuditPanel />}
      </main>
    </>
  )
}
