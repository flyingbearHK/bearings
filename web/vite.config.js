import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev` → http://localhost:5173 with /api proxied to `bearings serve` on :8765
// `npm run build` → writes the bundle into the Python package so `bearings serve` serves it
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  build: { outDir: '../bearings/static', emptyOutDir: true },
})
