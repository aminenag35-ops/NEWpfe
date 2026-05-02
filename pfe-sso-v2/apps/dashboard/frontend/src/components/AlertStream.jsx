const ICONS = {
  brute_force: '🔨',
  unusual_hour: '��',
  multi_ip: '🌐',
  ml_anomaly: '🤖',
}

function timeAgo(ts) {
  const diff = Math.floor((Date.now() - new Date(ts)) / 1000)
  if (diff < 60) return `il y a ${diff}s`
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)}m`
  return `il y a ${Math.floor(diff / 3600)}h`
}

export default function AlertStream({ alerts }) {
  return (
    <div>
      <div className="section-title">
        ⚡ Alertes en direct
        {alerts.length > 0 && <span className="counter-badge">{alerts.length}</span>}
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>🔍</div>
          En attente d'alertes…
        </div>
      ) : (
        <div className="alert-stream">
          {alerts.map(a => (
            <div key={a._id} className={`alert-item severity-${a.severity}`}>
              <div className="alert-header">
                <div className="alert-type">
                  {ICONS[a.alert_type] || '⚠️'}
                  {a.alert_type}
                  <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                </div>
                <div className="alert-time">{timeAgo(a.timestamp)}</div>
              </div>
              <div className="alert-meta">
                <span>👤 {a.username}</span>
                <span>🌐 {a.ip_address}</span>
                {a.score != null && <span>📈 {a.score.toFixed(3)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
