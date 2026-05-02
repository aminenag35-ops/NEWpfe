import { useState, useEffect, useCallback } from 'react'

function formatTTL(secs) {
  if (secs < 0) return 'Expiré'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function BlockedIPs() {
  const [ips, setIPs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    fetch('/api/blocked-ips')
      .then(r => r.ok ? r.json() : [])
      .then(setIPs)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [load])

  return (
    <div>
      <div className="section-title">
        🚫 IPs Bloquées
        {ips.length > 0 && <span className="counter-badge">{ips.length}</span>}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : ips.length === 0 ? (
        <div className="empty-state">Aucune IP bloquée</div>
      ) : (
        ips.map(item => (
          <div className="ip-item" key={item.ip}>
            <div>
              <div className="ip-addr">{item.ip}</div>
              <div className="ip-reason">{item.reason}</div>
            </div>
            <div className="ip-ttl">⏱ {formatTTL(item.ttl_seconds)}</div>
          </div>
        ))
      )}
    </div>
  )
}
