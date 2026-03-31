import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backendPort = process.env.VITE_BACKEND_PORT ?? '8000'
const backendHttpTarget = `http://localhost:${backendPort}`
const backendWsTarget = `ws://localhost:${backendPort}`

function isNodeModuleMatch(id: string, matcher: string | RegExp) {
  if (typeof matcher === 'string') {
    return id.includes(`/node_modules/${matcher}/`)
  }

  return matcher.test(id)
}

function matchesAnyNodeModule(id: string, matchers: Array<string | RegExp>) {
  return matchers.some((matcher) => isNodeModuleMatch(id, matcher))
}

export default defineConfig({
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 750,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')

          if (!normalizedId.includes('/node_modules/')) {
            return
          }

          if (matchesAnyNodeModule(normalizedId, ['react', 'react-dom', 'scheduler'])) {
            return 'react-vendor'
          }

          if (matchesAnyNodeModule(normalizedId, ['react-router', 'react-router-dom'])) {
            return 'router'
          }

          if (matchesAnyNodeModule(normalizedId, ['@tanstack/query-core', '@tanstack/react-query'])) {
            return 'query'
          }

          if (matchesAnyNodeModule(normalizedId, ['quill', 'parchment', 'quill-delta'])) {
            return 'editor'
          }

          if (matchesAnyNodeModule(normalizedId, ['recharts', 'victory-vendor', /\/node_modules\/d3-[^/]+\//])) {
            return 'charts'
          }

          return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': backendHttpTarget,
      '/ws': { target: backendWsTarget, ws: true },
    },
  },
})
