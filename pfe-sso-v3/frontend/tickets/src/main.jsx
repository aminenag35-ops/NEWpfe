import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import Keycloak from 'keycloak-js'
import App from './App.jsx'
import './index.css'

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: 'pfe',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT,
})

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } }
})

// On initialise Keycloak AVANT de monter React
keycloak
  .init({
    onLoad: 'login-required',     // Force le login dès l'arrivée
    pkceMethod: 'S256',           // PKCE sécurité
    checkLoginIframe: false,
  })
  .then((authenticated) => {
    if (!authenticated) {
      window.location.reload()
      return
    }

    // Refresh automatique du token toutes les 60s
    setInterval(() => {
      keycloak.updateToken(70).catch(() => keycloak.login())
    }, 60_000)

    // Notification au backend du login réussi (publication Kafka)
    fetch(`${import.meta.env.VITE_API_URL}/api/auth/notify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${keycloak.token}`,
      },
      body: JSON.stringify({ event_type: 'login_success', success: true })
    }).catch(console.error)

    ReactDOM.createRoot(document.getElementById('root')).render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <App keycloak={keycloak} />
          <Toaster position="top-right" />
        </QueryClientProvider>
      </React.StrictMode>
    )
  })
  .catch((err) => {
    console.error('Keycloak init failed:', err)
    document.getElementById('root').innerHTML =
      '<div class="p-8 text-red-600">Erreur d\'authentification Keycloak</div>'
  })
