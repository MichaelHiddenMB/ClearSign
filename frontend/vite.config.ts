import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI service runs on :8000 during development; /api is proxied to it
// so the client can use relative URLs in every environment.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
