import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Users, History, AlertTriangle, Ban, LogOut, Lock, Unlock, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api, setKeycloak } from './api.js'

const TABS = [
  { id: 'users',   label: 'Utilisateurs',  icon: Users },
  { id: 'events',  label: 'Événements',    icon: History },
  { id: 'alerts',  label: 'Alertes',       icon: AlertTriangle },
  { id: 'blocked', label: 'IPs bloquées',  icon: Ban },
]

export default function App({ keycloak }) {
  setKeycloak(keycloak)
  const [tab, setTab] = useState('users')
  const user = keycloak.tokenParsed
  const isAdmin = user?.realm_access?.roles?.includes('admin')

  if (!isAdmin) {
    return <div className="p-12 text-center text-red-600">
      Accès réservé aux administrateurs.
    </div>
  }

  return (
    <div className="min-h-screen">
      <Header user={user} onLogout={() => keycloak.logout()} />
      <main className="max-w-6xl mx-auto p-6">
        <Stats />
        <div className="bg-white rounded-xl border border-slate-200 mt-6">
          <nav className="flex border-b border-slate-200">
            {TABS.map(t => {
              const Icon = t.icon
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition
                    ${tab === t.id
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-slate-600 hover:text-slate-900'}`}>
                  <Icon className="w-4 h-4" />{t.label}
                </button>
              )
            })}
          </nav>
          <div className="p-4">
            {tab === 'users'   && <UsersTab />}
            {tab === 'events'  && <EventsTab />}
            {tab === 'alerts'  && <AlertsTab />}
            {tab === 'blocked' && <BlockedTab />}
          </div>
        </div>
      </main>
    </div>
  )
}

function Header({ user, onLogout }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-blue-600" />
          <h1 className="text-xl font-semibold">Console Admin</h1>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-700">{user?.preferred_username}</span>
          <button onClick={onLogout}
            className="flex items-center gap-2 px-3 py-2 text-slate-700 hover:bg-slate-100 rounded-lg">
            <LogOut className="w-4 h-4" /> Déconnexion
          </button>
        </div>
      </div>
    </header>
  )
}

function Stats() {
  const { data } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.get('/api/stats').then(r => r.data),
    refetchInterval: 5000,
  })
  if (!data) return null
  const items = [
    { label: 'Événements 24h',      value: data.events_24h,    color: 'blue' },
    { label: 'Alertes 24h',          value: data.alerts_24h,    color: 'red' },
    { label: 'IPs uniques 24h',      value: data.unique_ips_24h, color: 'amber' },
    { label: 'Utilisateurs bloqués', value: data.blocked_users, color: 'slate' },
  ]
  const colors = {
    blue:  'bg-blue-50 text-blue-700',
    red:   'bg-red-50 text-red-700',
    amber: 'bg-amber-50 text-amber-700',
    slate: 'bg-slate-50 text-slate-700',
  }
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map(it => (
        <div key={it.label} className={`rounded-xl p-4 ${colors[it.color]}`}>
          <div className="text-sm opacity-75">{it.label}</div>
          <div className="text-3xl font-semibold mt-1">{it.value}</div>
        </div>
      ))}
    </div>
  )
}

function UsersTab() {
  const qc = useQueryClient()
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users').then(r => r.data),
  })

  const block   = useMutation({ mutationFn: (id) => api.post(`/api/users/${id}/block`,   { reason: 'manual block' }),
                                onSuccess: () => { toast.success('Bloqué');  qc.invalidateQueries({ queryKey: ['users'] }) }})
  const unblock = useMutation({ mutationFn: (id) => api.post(`/api/users/${id}/unblock`),
                                onSuccess: () => { toast.success('Débloqué'); qc.invalidateQueries({ queryKey: ['users'] }) }})

  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-700">
        <tr>
          <th className="text-left px-4 py-2">Username</th>
          <th className="text-left px-4 py-2">Email</th>
          <th className="text-left px-4 py-2">Statut</th>
          <th className="text-right px-4 py-2">Actions</th>
        </tr>
      </thead>
      <tbody>
        {users.map(u => (
          <tr key={u.id} className="border-t border-slate-100">
            <td className="px-4 py-2 font-medium">{u.username}</td>
            <td className="px-4 py-2 text-slate-600">{u.email}</td>
            <td className="px-4 py-2">
              {u.is_blocked
                ? <span className="text-red-600 inline-flex items-center gap-1"><Lock className="w-3 h-3" /> Bloqué</span>
                : <span className="text-green-600 inline-flex items-center gap-1"><Unlock className="w-3 h-3" /> Actif</span>}
            </td>
            <td className="px-4 py-2 text-right">
              {u.is_blocked
                ? <button onClick={() => unblock.mutate(u.id)}
                          className="text-blue-600 hover:underline">Débloquer</button>
                : <button onClick={() => block.mutate(u.id)}
                          className="text-red-600 hover:underline">Bloquer</button>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EventsTab() {
  const { data: events = [] } = useQuery({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=100').then(r => r.data),
    refetchInterval: 3000,
  })
  return (
    <div className="space-y-1 font-mono text-xs">
      {events.map(e => (
        <div key={e.id} className="flex items-center gap-3 py-1 border-b border-slate-100">
          <span className="text-slate-400 w-44">{new Date(e.timestamp).toLocaleString('fr-FR')}</span>
          <span className={`px-2 py-0.5 rounded ${e.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {e.event_type}
          </span>
          <span className="font-medium">{e.username}</span>
          <span className="text-slate-500">{e.ip_address}</span>
        </div>
      ))}
    </div>
  )
}

function AlertsTab() {
  const { data: alerts = [] } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.get('/api/alerts?limit=100').then(r => r.data),
    refetchInterval: 3000,
  })
  const sevColors = {
    low:      'bg-slate-100 text-slate-700',
    medium:   'bg-amber-100 text-amber-700',
    high:     'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
  }
  return (
    <div className="space-y-2">
      {alerts.map(a => (
        <div key={a.id} className="flex items-center gap-3 p-3 border border-slate-200 rounded-lg">
          <span className={`px-2 py-1 rounded text-xs font-medium ${sevColors[a.severity] || sevColors.medium}`}>
            {a.severity}
          </span>
          <span className="font-medium text-slate-900">{a.alert_type}</span>
          <span className="text-slate-600">{a.username}</span>
          <span className="text-slate-500">{a.ip_address}</span>
          <span className="ml-auto text-xs text-slate-400">
            {new Date(a.timestamp).toLocaleString('fr-FR')}
          </span>
        </div>
      ))}
    </div>
  )
}

function BlockedTab() {
  const qc = useQueryClient()
  const { data: ips = [] } = useQuery({
    queryKey: ['blocked-ips'],
    queryFn: () => api.get('/api/blocked-ips').then(r => r.data),
    refetchInterval: 5000,
  })
  const unblockIp = useMutation({
    mutationFn: (ip) => api.delete(`/api/blocked-ips/${ip}`),
    onSuccess: () => { toast.success('IP débloquée'); qc.invalidateQueries({ queryKey: ['blocked-ips'] }) }
  })
  return (
    <div className="space-y-2">
      {ips.length === 0 && <div className="text-center text-slate-500 py-8">Aucune IP bloquée actuellement.</div>}
      {ips.map(ip => (
        <div key={ip.ip} className="flex items-center gap-3 p-3 border border-red-200 bg-red-50 rounded-lg">
          <Ban className="w-4 h-4 text-red-600" />
          <span className="font-mono font-medium">{ip.ip}</span>
          <span className="text-sm text-slate-600">{ip.reason}</span>
          <span className="text-xs text-slate-400">expire dans {Math.round(ip.ttl_seconds / 60)} min</span>
          <button onClick={() => unblockIp.mutate(ip.ip)}
                  className="ml-auto p-1 text-red-600 hover:bg-red-100 rounded">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
