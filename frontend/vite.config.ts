import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API base URL is injected at build time; defaults to localhost for dev.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: true,
    port: 5173,
  },
})
