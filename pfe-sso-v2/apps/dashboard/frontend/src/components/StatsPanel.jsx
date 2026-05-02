import { useState, useEffect, useCallback } from 'react'

export default function StatsPanel() {
  const [stats, setStats] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    fetch('/api/stats')
      .then(r => r.ok ? r.json() : [])
      .then(setStats)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  const totals = stats.reduce((acc, s) => {
    acc[s.severity] = (acc[s.severity] || 0) + Number(s.count)
    return acc
  }, {})

  const SEVS = [
    { key: 'critical', label: 'Critical', color: 'var(--critical)' },
    { key: 'high', label: 'High', color: 'var(--high)' },
    { key: 'medium', label: 'Medium', color: 'var(--medium)' },
    { key: 'low', label: 'Low', color: 'var(--low)' },
  ]

  return (
    <div>
      <div className="section-title">📊 Statistiques — dernières 24h</div>
      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : (
        <div className="stats-grid">
          {SEVS.map(s => (
            <div className="stat-card" key={s.key}>
              <div className="stat-value" style={{ color: s.color }}>
                {totals[s.key] || 0}
              </div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
