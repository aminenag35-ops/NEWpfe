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

keycloak
  .init({ onLoad: 'login-required', pkceMethod: 'S256', checkLoginIframe: false })
  .then((authenticated) => {
    if (!authenticated) { window.location.reload(); return }
    setInterval(() => {
      keycloak.updateToken(70).catch(() => keycloak.login())
    }, 60_000)
    ReactDOM.createRoot(document.getElementById('root')).render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <App keycloak={keycloak} />
          <Toaster position="top-right" />
        </QueryClientProvider>
      </React.StrictMode>
    )
  })
  .catch(console.error)
