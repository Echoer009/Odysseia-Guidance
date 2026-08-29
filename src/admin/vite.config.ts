import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/admin/',
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash]-v2.js',
        chunkFileNames: 'assets/[name]-[hash]-v2.js',
        assetFileNames: 'assets/[name]-[hash]-v2.[ext]',
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    host: true,
    port: 3004,
    proxy: {
      '/admin/api': {
        target: 'http://127.0.0.1:8004',
        rewrite: (path) => path.replace(/^\/admin/, ''),
        changeOrigin: true,
      },
      '/admin/callback': {
        target: 'http://127.0.0.1:8004',
        rewrite: (path) => path.replace(/^\/admin/, ''),
        changeOrigin: true,
      },
    },
  },
})
