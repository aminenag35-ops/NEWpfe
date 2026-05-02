import { useState, useEffect, useCallback } from 'react'

export default function BlockedIPsPanel() {
  const [ips, setIPs] = useState([])
  const [loading, setLoading] = useState(true)
  const [removing, setRemoving] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/blocked-ips')
      .then(r => r.json())
      .then(setIPs)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const unblock = async (ip) => {
    if (!window.confirm(`Débloquer l'IP ${ip} ?`)) return
    setRemoving(ip)
    await fetch(`/api/blocked-ips/${encodeURIComponent(ip)}`, { method: 'DELETE' })
    await load()
    setRemoving(null)
  }

  const formatTTL = (secs) => {
    if (secs < 0) return 'Expiré'
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div>
      <div className="page-title">🚫 IPs Bloquées</div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            IPs actuellement bloquées dans Redis ({ips.length})
          </div>
          <button className="refresh-btn" onClick={load}>↻ Rafraîchir</button>
        </div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Chargement…</div>
        ) : ips.length === 0 ? (
          <div className="empty-state">
            <div style={{ fontSize: '2rem', marginBottom: 8 }}>✅</div>
            Aucune IP bloquée
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Adresse IP</th>
                <th>Raison</th>
                <th>TTL restant</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {ips.map(item => (
                <tr key={item.ip}>
                  <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                    {item.ip}
                  </td>
                  <td>
                    <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4, fontSize: '0.8rem' }}>
                      {item.reason || '—'}
                    </code>
                  </td>
                  <td style={{ fontFamily: 'monospace', color: item.ttl_seconds < 300 ? 'var(--warning)' : 'var(--text)' }}>
                    {formatTTL(item.ttl_seconds)}
                  </td>
                  <td>
                    <button
                      className="btn-danger"
                      disabled={removing === item.ip}
                      onClick={() => unblock(item.ip)}
                      style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                    >
                      {removing === item.ip ? '…' : 'Débloquer'}
                    </button>
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
