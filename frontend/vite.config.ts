import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5001,
    // Let the dev server read ../contracts (sample results shown until analysis is connected).
    // Setting `allow` replaces the default, so the project root is listed explicitly.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../contracts'] },
    // Frontend calls /api/*, Vite forwards to the FastAPI backend (no CORS needed in dev).
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
