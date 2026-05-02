import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5002',
      '/login': 'http://localhost:5002',
      '/logout': 'http://localhost:5002',
      '/callback': 'http://localhost:5002',
    },
  },
})
