import { useState, useEffect } from 'react'

const PRIORITY_COLORS = { high: 'priority-high', medium: 'priority-medium', low: 'priority-low' }
const STATUS_COLORS = { open: 'status-open', closed: 'status-closed', in_progress: 'status-in_progress' }

export default function TicketsList() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    fetch('/api/tickets')
      .then(r => r.json())
      .then(data => Array.isArray(data) ? setTickets(data) : setTickets([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = tickets.filter(t =>
    !filter || t.title?.toLowerCase().includes(filter.toLowerCase()) ||
    t.description?.toLowerCase().includes(filter.toLowerCase())
  )

  if (loading) return (
    <div className="loading"><div className="spinner" /> Chargement…</div>
  )

  return (
    <div>
      {tickets.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <input
            type="search"
            placeholder="Rechercher un ticket…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🎫</div>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Aucun ticket</div>
          <div>Créez votre premier ticket avec le bouton ci-dessus.</div>
        </div>
      ) : (
        <div className="ticket-list">
          {filtered.map(t => (
            <div className="ticket-card" key={t.id}>
              <div className="ticket-header">
                <div>
                  <div className="ticket-id">#{t.id}</div>
                  <div className="ticket-title">{t.title}</div>
                </div>
                <span className={`status-badge ${STATUS_COLORS[t.status] || 'status-open'}`}>
                  {t.status || 'open'}
                </span>
              </div>
              {t.description && (
                <div className="ticket-desc">{t.description}</div>
              )}
              <div className="ticket-footer">
                {t.priority && (
                  <span className={`priority-badge ${PRIORITY_COLORS[t.priority] || ''}`}>
                    {t.priority}
                  </span>
                )}
                <span>
                  {t.created_at
                    ? new Date(t.created_at).toLocaleDateString('fr-FR', {
                        day: '2-digit', month: 'short', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                      })
                    : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
