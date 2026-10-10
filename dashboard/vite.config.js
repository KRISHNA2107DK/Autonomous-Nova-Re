import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development (`npm run dev` on :5173) the API and WebSocket are proxied to
// the NovaSurge server, so the app always uses same-origin relative URLs and
// works unchanged when served by the API itself on :8000.
const API = process.env.NOVASURGE_API || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': API,
      '/ws': { target: API.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
})
