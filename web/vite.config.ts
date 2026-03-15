import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backendPort = process.env.VITE_BACKEND_PORT ?? '8000'
const backendHttpTarget = `http://localhost:${backendPort}`
const backendWsTarget = `ws://localhost:${backendPort}`

export default defineConfig({
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': backendHttpTarget,
      '/ws': { target: backendWsTarget, ws: true },
    },
  },
})
