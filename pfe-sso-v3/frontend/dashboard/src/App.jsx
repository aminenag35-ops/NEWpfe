import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Bell, ShieldAlert, TrendingUp, LogOut, Wifi, WifiOff } from 'lucide-react'
import { api, setKeycloak } from './api.js'

const SEVERITY_STYLES = {
  low:      { bg: 'bg-slate-50',   border: 'border-slate-300',   text: 'text-slate-700',   pill: 'bg-slate-200' },
  medium:   { bg: 'bg-amber-50',   border: 'border-amber-300',   text: 'text-amber-800',   pill: 'bg-amber-200' },
  high:     { bg: 'bg-orange-50',  border: 'border-orange-400',  text: 'text-orange-800',  pill: 'bg-orange-200' },
  critical: { bg: 'bg-red-50',     border: 'border-red-400',     text: 'text-red-800',     pill: 'bg-red-200' },
}

export default function App({ keycloak }) {
  setKeycloak(keycloak)
  const user = keycloak.tokenParsed
  const [liveAlerts, setLiveAlerts] = useState([])
  const [wsConnected, setWsConnected] = useState(false)

  const { data: stats = [] } = useQuery({
    queryKey: ['ws-stats'],
    queryFn: () => api.get('/api/stats').then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: history = [] } = useQuery({
    queryKey: ['alerts-history'],
    queryFn: () => api.get('/api/alerts?limit=20').then(r => r.data),
  })

  // -------------------------------------------------------------------------
  // WebSocket : alertes en temps réel
  // -------------------------------------------------------------------------
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_API_URL.replace(/^http/, 'ws')
    const token = keycloak.token
    const ws = new WebSocket(`${wsUrl}/ws/alerts?token=${token}`)

    ws.onopen = () => setWsConnected(true)
    ws.onclose = () => setWsConnected(false)
    ws.onerror = () => setWsConnected(false)

    ws.onmessage = (e) => {
      try {
        const alert = JSON.parse(e.data)
        setLiveAlerts(prev => [alert, ...prev].slice(0, 50))
      } catch (err) { console.error(err) }
    }
    return () => ws.close()
  }, [keycloak.token])

  // Fusion : alertes live + historique, dédoublonné par alert_id
  const merged = [
    ...liveAlerts,
    ...history.filter(h => !liveAlerts.find(l => l.alert_id === h.alert_id || l.id === h.id))
  ].slice(0, 50)

  return (
    <div className="min-h-screen">
      <Header user={user} wsConnected={wsConnected} onLogout={() => keycloak.logout()} />
      <main className="max-w-6xl mx-auto p-6 space-y-6">
        <StatsCards stats={stats} totalLive={liveAlerts.length} />
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <AlertFeed alerts={merged} />
          </div>
          <ByTypeCard stats={stats} />
        </div>
      </main>
    </div>
  )
}

function Header({ user, wsConnected, onLogout }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-6 h-6 text-red-600" />
          <h1 className="text-xl font-semibold">Centre de supervision</h1>
          <span className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
            wsConnected ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
          }`}>
            {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {wsConnected ? 'temps réel' : 'déconnecté'}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span>{user?.preferred_username}</span>
          <button onClick={onLogout}
            className="flex items-center gap-2 px-3 py-2 text-slate-700 hover:bg-slate-100 rounded-lg">
            <LogOut className="w-4 h-4" /> Déconnexion
          </button>
        </div>
      </div>
    </header>
  )
}

function StatsCards({ stats, totalLive }) {
  const total = stats.reduce((acc, s) => acc + Number(s.count), 0)
  const critical = stats
    .filter(s => s.severity === 'critical')
    .reduce((acc, s) => acc + Number(s.count), 0)
  const items = [
    { label: 'Alertes 24h',     value: total,       icon: Bell,        color: 'blue' },
    { label: 'Critiques',       value: critical,    icon: ShieldAlert, color: 'red' },
    { label: 'Live cette session', value: totalLive, icon: Activity,    color: 'green' },
    { label: 'Types détectés',  value: stats.length, icon: TrendingUp, color: 'amber' },
  ]
  const colors = {
    blue:  'bg-blue-50 text-blue-700',
    red:   'bg-red-50 text-red-700',
    green: 'bg-green-50 text-green-700',
    amber: 'bg-amber-50 text-amber-700',
  }
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {items.map(it => {
        const Icon = it.icon
        return (
          <div key={it.label} className={`rounded-xl p-4 ${colors[it.color]}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm opacity-75">{it.label}</span>
              <Icon className="w-5 h-5 opacity-60" />
            </div>
            <div className="text-3xl font-semibold mt-1">{it.value}</div>
          </div>
        )
      })}
    </div>
  )
}

function AlertFeed({ alerts }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200">
      <div className="px-4 py-3 border-b border-slate-200 flex items-center gap-2">
        <Bell className="w-5 h-5 text-slate-600" />
        <h2 className="font-semibold">Flux d'alertes</h2>
      </div>
      <div className="max-h-[600px] overflow-y-auto">
        {alerts.length === 0 && (
          <div className="p-12 text-center text-slate-500">
            Aucune alerte. En attente d'événements...
          </div>
        )}
        {alerts.map((a, idx) => {
          const s = SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.medium
          return (
            <div key={a.alert_id || a.id || idx}
                 className={`p-4 border-l-4 ${s.border} ${s.bg} ${idx > 0 ? 'border-t border-slate-100' : ''}`}>
              <div className="flex items-start gap-3">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${s.pill} ${s.text}`}>
                  {a.severity}
                </span>
                <div className="flex-1">
                  <div className={`font-medium ${s.text}`}>{a.alert_type}</div>
                  <div className="text-sm text-slate-600 mt-1">
                    Utilisateur <strong>{a.username || '?'}</strong> · IP <code>{a.ip_address || '?'}</code>
                  </div>
                  {a.score && (
                    <div className="text-xs text-slate-500 mt-1">
                      Score: {Number(a.score).toFixed(2)}
                    </div>
                  )}
                </div>
                <div className="text-xs text-slate-400 whitespace-nowrap">
                  {new Date(a.timestamp).toLocaleTimeString('fr-FR')}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ByTypeCard({ stats }) {
  const grouped = stats.reduce((acc, s) => {
    acc[s.alert_type] = (acc[s.alert_type] || 0) + Number(s.count)
    return acc
  }, {})
  const max = Math.max(1, ...Object.values(grouped))
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <h2 className="font-semibold mb-4">Par type d'attaque</h2>
      <div className="space-y-3">
        {Object.entries(grouped).map(([type, count]) => (
          <div key={type}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium text-slate-700">{type}</span>
              <span className="text-slate-500">{count}</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500" style={{ width: `${(count / max) * 100}%` }} />
            </div>
          </div>
        ))}
        {Object.keys(grouped).length === 0 && (
          <div className="text-sm text-slate-500">Pas encore de données.</div>
        )}
      </div>
    </div>
  )
}
