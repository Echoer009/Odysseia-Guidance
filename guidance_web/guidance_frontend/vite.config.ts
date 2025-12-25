import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // 将所有 /api 开头的请求代理到 FastAPI 后端
      // 目标地址是我们的后端服务。在本地开发中，
      // 我们假设 FastAPI 运行在 8000 端口。
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
