import { useState, useEffect, useCallback } from 'react'

export default function AuditPanel() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterUser, setFilterUser] = useState('')
  const [filterAction, setFilterAction] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/audit')
      .then(r => r.json())
      .then(setLogs)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const actions = [...new Set(logs.map(l => l.action))].sort()

  const filtered = logs
    .filter(l => !filterUser || l.username?.toLowerCase().includes(filterUser.toLowerCase()))
    .filter(l => !filterAction || l.action === filterAction)

  return (
    <div>
      <div className="page-title">📋 Journal d'Audit</div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Entrées d'audit ({filtered.length})</div>
          <button className="refresh-btn" onClick={load}>↻ Rafraîchir</button>
        </div>

        <div className="filter-row">
          <input
            type="search"
            placeholder="Filtrer par utilisateur…"
            value={filterUser}
            onChange={e => setFilterUser(e.target.value)}
            style={{ width: 220 }}
          />
          <select value={filterAction} onChange={e => setFilterAction(e.target.value)}>
            <option value="">Toutes actions</option>
            {actions.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Chargement…</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">Aucune entrée d'audit</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date/Heure</th>
                <th>Utilisateur</th>
                <th>Action</th>
                <th>IP</th>
                <th>Succès</th>
                <th>Détails</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(l => (
                <tr key={l.id}>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(l.timestamp).toLocaleString('fr-FR')}
                  </td>
                  <td style={{ fontWeight: 500 }}>{l.username || '—'}</td>
                  <td>
                    <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4, fontSize: '0.8rem' }}>
                      {l.action}
                    </code>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {l.ip_address || '—'}
                  </td>
                  <td>
                    {l.success == null ? '—' : (
                      <span className={`badge ${l.success ? 'badge-active' : 'badge-blocked'}`}>
                        {l.success ? '✓' : '✗'}
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', maxWidth: 200 }}>
                    {l.details ? JSON.stringify(l.details).substring(0, 80) : '—'}
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
