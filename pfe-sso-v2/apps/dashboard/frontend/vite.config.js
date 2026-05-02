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
      '/api': 'http://localhost:5003',
      '/login': 'http://localhost:5003',
      '/logout': 'http://localhost:5003',
      '/callback': 'http://localhost:5003',
      '/socket.io': {
        target: 'http://localhost:5003',
        ws: true,
      },
    },
  },
})
