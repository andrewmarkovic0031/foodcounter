import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// In dev (`npm run dev`) API calls are proxied to the FastAPI server.
// In production FastAPI serves the built files itself, so no proxy is needed.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
