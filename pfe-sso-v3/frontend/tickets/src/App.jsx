import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut, Plus, Ticket as TicketIcon, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { api, setKeycloak } from './api.js'

const PRIORITY_COLORS = {
  low:      'bg-slate-100 text-slate-700',
  medium:   'bg-blue-100 text-blue-700',
  high:     'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

const STATUS_ICONS = {
  open:        <Clock className="w-4 h-4" />,
  in_progress: <AlertCircle className="w-4 h-4" />,
  resolved:    <CheckCircle2 className="w-4 h-4" />,
}

export default function App({ keycloak }) {
  setKeycloak(keycloak)
  const qc = useQueryClient()
  const user = keycloak.tokenParsed

  const { data: tickets = [], isLoading } = useQuery({
    queryKey: ['tickets'],
    queryFn: () => api.get('/api/tickets').then(r => r.data),
    refetchInterval: 5000,
  })

  const createMutation = useMutation({
    mutationFn: (body) => api.post('/api/tickets', body),
    onSuccess: () => {
      toast.success('Ticket créé')
      qc.invalidateQueries({ queryKey: ['tickets'] })
    },
    onError: () => toast.error('Erreur lors de la création'),
  })

  return (
    <div className="min-h-screen">
      <Header user={user} onLogout={() => keycloak.logout()} />
      <main className="max-w-5xl mx-auto p-6">
        <NewTicketCard onSubmit={(body) => createMutation.mutate(body)}
                       isLoading={createMutation.isPending} />
        <TicketList tickets={tickets} isLoading={isLoading} />
      </main>
    </div>
  )
}


function Header({ user, onLogout }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TicketIcon className="w-6 h-6 text-blue-600" />
          <h1 className="text-xl font-semibold text-slate-900">Tickets</h1>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="text-right">
            <div className="font-medium text-slate-900">{user?.preferred_username}</div>
            <div className="text-slate-500 text-xs">
              {user?.realm_access?.roles?.filter(r => ['admin','manager','user'].includes(r)).join(', ')}
            </div>
          </div>
          <button onClick={onLogout}
                  className="flex items-center gap-2 px-3 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition">
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Déconnexion</span>
          </button>
        </div>
      </div>
    </header>
  )
}


function NewTicketCard({ onSubmit, isLoading }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('medium')

  function submit(e) {
    e.preventDefault()
    if (!title.trim()) return
    onSubmit({ title, description, priority })
    setTitle(''); setDescription(''); setPriority('medium')
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h2 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
        <Plus className="w-5 h-5 text-blue-600" /> Nouveau ticket
      </h2>
      <form onSubmit={submit} className="space-y-3">
        <input type="text" value={title} onChange={e => setTitle(e.target.value)}
               placeholder="Titre du ticket"
               className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
        <textarea value={description} onChange={e => setDescription(e.target.value)}
                  placeholder="Description (optionnel)" rows={3}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
        <div className="flex items-center gap-3">
          <select value={priority} onChange={e => setPriority(e.target.value)}
                  className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
            <option value="low">Faible</option>
            <option value="medium">Moyenne</option>
            <option value="high">Haute</option>
            <option value="critical">Critique</option>
          </select>
          <button type="submit" disabled={isLoading || !title.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition">
            {isLoading ? 'Envoi...' : 'Créer'}
          </button>
        </div>
      </form>
    </div>
  )
}


function TicketList({ tickets, isLoading }) {
  if (isLoading) return <div className="text-center py-12 text-slate-500">Chargement...</div>
  if (!tickets.length) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
        Aucun ticket. Créez-en un ci-dessus.
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {tickets.map(t => (
        <div key={t.id} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-sm transition">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-slate-400">#{t.id}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[t.priority]}`}>
                  {t.priority}
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  {STATUS_ICONS[t.status]} {t.status}
                </span>
              </div>
              <h3 className="font-medium text-slate-900">{t.title}</h3>
              {t.description && (
                <p className="text-sm text-slate-600 mt-1 line-clamp-2">{t.description}</p>
              )}
            </div>
            <div className="text-xs text-slate-400">
              {new Date(t.created_at).toLocaleString('fr-FR')}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
