import { useState } from 'react'

export default function NewTicketModal({ onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('medium')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!title.trim()) { setError('Le titre est requis'); return }

    setSubmitting(true)
    setError('')
    try {
      const r = await fetch('/api/tickets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), description, priority }),
      })
      const data = await r.json()
      if (!r.ok) { setError(data.error || 'Erreur lors de la création'); return }
      onCreated(data)
    } catch {
      setError('Erreur réseau')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-title">🎫 Nouveau Ticket</div>

        {error && (
          <div className="alert-banner alert-error">⚠️ {error}</div>
        )}

        <form onSubmit={submit}>
          <div className="form-group">
            <label>Titre *</label>
            <input
              type="text"
              placeholder="Décrivez brièvement votre problème…"
              value={title}
              onChange={e => setTitle(e.target.value)}
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              placeholder="Détails supplémentaires (optionnel)…"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label>Priorité</label>
            <select value={priority} onChange={e => setPriority(e.target.value)}>
              <option value="low">🟢 Basse</option>
              <option value="medium">🟡 Moyenne</option>
              <option value="high">🔴 Haute</option>
            </select>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? '…' : '✓ Créer le ticket'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
