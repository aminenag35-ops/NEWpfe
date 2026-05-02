import { useState, useEffect, useCallback } from 'react'

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterSeverity, setFilterSeverity] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterUser, setFilterUser] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/alerts')
      .then(r => r.json())
      .then(setAlerts)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const types = [...new Set(alerts.map(a => a.alert_type))].sort()

  const filtered = alerts
    .filter(a => !filterSeverity || a.severity === filterSeverity)
    .filter(a => !filterType || a.alert_type === filterType)
    .filter(a => !filterUser || a.username?.toLowerCase().includes(filterUser.toLowerCase()))

  const counts = { critical: 0, high: 0, medium: 0, low: 0 }
  alerts.forEach(a => { if (a.severity in counts) counts[a.severity]++ })

  return (
    <div>
      <div className="page-title">🚨 Alertes de Sécurité ML</div>

      <div className="stats-grid">
        {Object.entries(counts).map(([sev, count]) => (
          <div className="stat-card" key={sev}>
            <div className={`stat-value`} style={{
              color: sev === 'critical' ? 'var(--critical)' :
                     sev === 'high' ? 'var(--high)' :
                     sev === 'medium' ? 'var(--warning)' : 'var(--low)'
            }}>
              {count}
            </div>
            <div className="stat-label">{sev.charAt(0).toUpperCase() + sev.slice(1)}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Alertes ({filtered.length})</div>
          <button className="refresh-btn" onClick={load}>↻ Rafraîchir</button>
        </div>

        <div className="filter-row">
          <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}>
            <option value="">Toutes sévérités</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="">Tous types</option>
            {types.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <input
            type="search"
            placeholder="Filtrer par utilisateur…"
            value={filterUser}
            onChange={e => setFilterUser(e.target.value)}
            style={{ width: 220 }}
          />
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Chargement…</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">Aucune alerte</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date/Heure</th>
                <th>Utilisateur</th>
                <th>IP</th>
                <th>Type</th>
                <th>Sévérité</th>
                <th>Score</th>
                <th>Détails</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(a => (
                <tr key={a.id}>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(a.timestamp).toLocaleString('fr-FR')}
                  </td>
                  <td style={{ fontWeight: 500 }}>{a.username}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{a.ip_address}</td>
                  <td>
                    <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4, fontSize: '0.8rem' }}>
                      {a.alert_type}
                    </code>
                  </td>
                  <td>
                    <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {a.score?.toFixed(3)}
                  </td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', maxWidth: 200 }}>
                    {a.details ? JSON.stringify(a.details).substring(0, 80) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
