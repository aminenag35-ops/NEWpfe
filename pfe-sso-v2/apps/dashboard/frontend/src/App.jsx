import { useState, useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import AlertStream from './components/AlertStream'
import StatsPanel from './components/StatsPanel'
import RecentAlerts from './components/RecentAlerts'
import BlockedIPs from './components/BlockedIPs'

const MAX_LIVE_ALERTS = 100

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [liveAlerts, setLiveAlerts] = useState([])
  const [alertCount, setAlertCount] = useState(0)
  const socketRef = useRef(null)

  // Auth check
  useEffect(() => {
    fetch('/api/me')
      .then(r => {
        if (r.status === 401) { window.location.href = '/login'; return null }
        return r.json()
      })
      .then(data => { if (data) setUser(data) })
      .finally(() => setLoading(false))
  }, [])

  // Socket.IO connection
  useEffect(() => {
    if (!user) return

    const socket = io(window.location.origin, { transports: ['websocket', 'polling'] })
    socketRef.current = socket

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('new_alert', (alert) => {
      setLiveAlerts(prev => [{ ...alert, _id: Date.now() + Math.random() }, ...prev].slice(0, MAX_LIVE_ALERTS))
      setAlertCount(c => c + 1)
    })

    return () => socket.disconnect()
  }, [user])

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
        <div className="navbar-brand">
          📊 Dashboard Sécurité
          <span className={`status-dot ${connected ? '' : 'offline'}`} title={connected ? 'Connecté' : 'Déconnecté'} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>
            {connected ? 'Live' : 'Reconnexion…'}
          </span>
        </div>
        <div className="navbar-right">
          {alertCount > 0 && (
            <span style={{ color: 'var(--danger)', fontWeight: 600 }}>
              🚨 {alertCount} alerte{alertCount > 1 ? 's' : ''} reçue{alertCount > 1 ? 's' : ''}
            </span>
          )}
          <span>{user.username}</span>
          <a href="/logout">Déconnexion</a>
        </div>
      </nav>

      <div className="layout">
        <div className="main-panel">
          <StatsPanel />
          <div style={{ marginTop: 20 }}>
            <RecentAlerts />
          </div>
        </div>

        <div className="side-panel">
          <AlertStream alerts={liveAlerts} />
          <div style={{ marginTop: 24 }}>
            <BlockedIPs />
          </div>
        </div>
      </div>
    </>
  )
}
