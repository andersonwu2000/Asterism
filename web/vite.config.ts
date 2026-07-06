import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev server proxies API calls to a locally running `asterism serve`
// (default port 8642). Production build is served by FastAPI itself,
// so the proxy only matters during `npm run dev`.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8642',
    },
  },
})
