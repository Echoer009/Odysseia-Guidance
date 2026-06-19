import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/diary/',
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  envDir: '../../',
  server: {
    host: true,
    port: 3001,
    hmr: false,
    proxy: {
      '/diary/api': {
        target: 'http://127.0.0.1:8003',
        rewrite: (path) => path.replace(/^\/diary/, ''),
        changeOrigin: true,
      },
    },
  },
})
