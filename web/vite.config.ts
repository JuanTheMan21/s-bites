/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const DEV_BACKEND = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // src/api/base-url.ts's own comment explains why this is /api, not a bare backend passthrough:
    // the backend's routes (/jobs, /jobs/{id}) are identical strings to this app's own client-side
    // routes, so a bare-path proxy would swallow a real browser navigation to the frontend's own
    // /jobs page before React Router ever saw it. Stripped here so the backend's route paths never
    // have to know this prefix exists.
    proxy: {
      '/api': {
        target: DEV_BACKEND,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
