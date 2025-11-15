import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
    base: '/',
    publicDir: 'public',
    plugins: [vue()],
    // 设置环境变量目录为项目的根目录 (修正路径)
    envDir: '../../../../../',
    server: {
        host: true, // 允许来自任何地址的连接
        hmr: false, // 禁用HMR以解决Discord CSP问题
        allowedHosts: ['bring-optional-models-interviews.trycloudflare.com', '.trycloudflare.com'], // 允许Cloudflare隧道主机
        proxy: {
            // 将所有/api开头的请求代理到Python后端
            '/api': {
                target: 'http://127.0.0.1:8000', // 您的FastAPI服务器地址
                changeOrigin: true,
                // The rewrite rule has been removed to ensure the /api prefix is forwarded to the backend,
                // matching the FastAPI router definition (e.g., @app.get("/api/user")).
            },
        },
    },
});