import { defineConfig } from 'vite'

export default defineConfig({
  base: '/',
  envDir: '../../',
  server: {
    host: true,
    port: 3002,
    hmr: false,
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
    },
  },
})
