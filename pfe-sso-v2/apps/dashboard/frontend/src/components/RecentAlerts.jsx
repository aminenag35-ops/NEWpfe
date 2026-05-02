import { useState, useEffect, useCallback } from 'react'

const ICONS = { brute_force: '🔨', unusual_hour: '🌙', multi_ip: '🌐', ml_anomaly: '🤖' }

export default function RecentAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/alerts/recent')
      .then(r => r.ok ? r.json() : [])
      .then(setAlerts)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>🗂️ 50 dernières alertes</span>
        <button className="btn-ghost" onClick={load} style={{ fontSize: '0.75rem', padding: '3px 8px' }}>↻</button>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : alerts.length === 0 ? (
        <div className="empty-state">Aucune alerte récente</div>
      ) : (
        <div className="recent-table">
          <table>
            <thead>
              <tr>
                <th>Heure</th>
                <th>Utilisateur</th>
                <th>IP</th>
                <th>Type</th>
                <th>Sévérité</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(a => (
                <tr key={a.id}>
                  <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(a.timestamp).toLocaleTimeString('fr-FR')}
                  </td>
                  <td style={{ fontWeight: 500 }}>{a.username}</td>
                  <td style={{ fontFamily: 'monospace' }}>{a.ip_address}</td>
                  <td>
                    {ICONS[a.alert_type] || '⚠️'} {a.alert_type}
                  </td>
                  <td>
                    <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                  </td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                    {a.score?.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
