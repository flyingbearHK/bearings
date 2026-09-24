import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev` → http://localhost:5173 with /api proxied to `bearings serve` on :8765
// `npm run build` → writes the bundle into the Python package so `bearings serve` serves it
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  // the app itself is ~300 kB; the big chunks are Mermaid's diagram renderers, loaded only when the ER diagram opens
  build: { outDir: '../bearings/static', emptyOutDir: true, chunkSizeWarningLimit: 2500 },
})
