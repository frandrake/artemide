import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

// Proxy /api/v1 and /mcp to the local FastAPI server during dev.
// Production deployments serve the built static files from FastAPI,
// so no proxy is needed there.
export default defineConfig({
  output: 'static',
  integrations: [react()],
  server: { host: '0.0.0.0', port: 4321 },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        '/api/v1': { target: 'http://localhost:8000', changeOrigin: true },
        '/mcp': { target: 'http://localhost:8000', changeOrigin: true },
        '/login': { target: 'http://localhost:8000', changeOrigin: true },
        '/logout': { target: 'http://localhost:8000', changeOrigin: true },
        '/health': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
  },
});
