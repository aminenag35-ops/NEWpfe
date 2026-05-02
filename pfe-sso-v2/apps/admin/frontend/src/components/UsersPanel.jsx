import { useState, useEffect, useCallback } from 'react'

export default function UsersPanel() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [blockingId, setBlockingId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/users')
      .then(r => r.json())
      .then(setUsers)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const blockUser = async (id, reason = 'manual block') => {
    setBlockingId(id)
    await fetch(`/api/users/${id}/block`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    })
    await load()
    setBlockingId(null)
  }

  const unblockUser = async (id) => {
    setBlockingId(id)
    await fetch(`/api/users/${id}/unblock`, { method: 'POST' })
    await load()
    setBlockingId(null)
  }

  const filtered = users.filter(u =>
    u.username?.toLowerCase().includes(filter.toLowerCase()) ||
    u.email?.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div>
      <div className="page-title">👥 Gestion des Utilisateurs</div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{users.length}</div>
          <div className="stat-label">Total</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--success)' }}>
            {users.filter(u => !u.is_blocked).length}
          </div>
          <div className="stat-label">Actifs</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--danger)' }}>
            {users.filter(u => u.is_blocked).length}
          </div>
          <div className="stat-label">Bloqués</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Liste des utilisateurs</div>
          <button className="refresh-btn" onClick={load}>↻ Rafraîchir</button>
        </div>

        <div className="filter-row">
          <input
            type="search"
            placeholder="Filtrer par nom ou email…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{ width: 280 }}
          />
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Chargement…</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">Aucun utilisateur trouvé</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Nom d'utilisateur</th>
                <th>Email</th>
                <th>Statut</th>
                <th>Créé le</th>
                <th>Raison blocage</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id}>
                  <td style={{ color: 'var(--text-muted)' }}>{u.id}</td>
                  <td style={{ fontWeight: 500 }}>{u.username}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{u.email || '—'}</td>
                  <td>
                    <span className={`badge ${u.is_blocked ? 'badge-blocked' : 'badge-active'}`}>
                      {u.is_blocked ? '🔒 Bloqué' : '✅ Actif'}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('fr-FR') : '—'}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {u.blocked_reason || '—'}
                  </td>
                  <td>
                    <div className="action-group">
                      {u.is_blocked ? (
                        <button
                          className="btn-success"
                          disabled={blockingId === u.id}
                          onClick={() => unblockUser(u.id)}
                          style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                        >
                          Débloquer
                        </button>
                      ) : (
                        <button
                          className="btn-danger"
                          disabled={blockingId === u.id}
                          onClick={() => {
                            const reason = window.prompt('Raison du blocage:', 'manual block')
                            if (reason !== null) blockUser(u.id, reason)
                          }}
                          style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                        >
                          Bloquer
                        </button>
                      )}
                    </div>
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
