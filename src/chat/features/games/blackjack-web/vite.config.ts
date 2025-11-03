import { defineConfig } from 'vite';

export default defineConfig({
    // 设置环境变量目录为项目的根目录 (修正路径)
    envDir: '../../../../../',
    server: {
        proxy: {
            // 将所有/api开头的请求代理到Python后端
            '/api': {
                target: 'http://12-7.0.0.1:8000', // 您的FastAPI服务器地址
                changeOrigin: true,
            },
        },
    },
});