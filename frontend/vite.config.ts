import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: the API runs on :8000 (python app.py --no-browser). Build output goes to dist/, which the API serves.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
