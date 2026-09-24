import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
    base: '/riddle/',
    plugins: [vue()],
    envDir: '../../../../../',
    server: {
        host: true,
        hmr: false,
        allowedHosts: ['.trycloudflare.com'],
        proxy: {
            '/riddle/api': {
                target: 'http://127.0.0.1:8005',
                rewrite: (path) => path.replace(/^\/riddle/, ''),
                changeOrigin: true,
            },
        },
    },
});
