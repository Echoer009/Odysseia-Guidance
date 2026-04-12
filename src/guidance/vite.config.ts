import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/guidance/',
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  envDir: '../../',
  server: {
    host: true,
    port: 3000,
    hmr: false,
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/guidance/api': {
        target: 'http://127.0.0.1:8001',
        rewrite: (path) => path.replace(/^\/guidance/, ''),
        changeOrigin: true,
      },
    },
  },
})
