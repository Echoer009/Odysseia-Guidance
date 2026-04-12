import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
    base: '/blackjack/',
    publicDir: 'public',
    plugins: [vue()],
    envDir: '../../../../../',
    server: {
        host: true,
        hmr: false,
        allowedHosts: ['bring-optional-models-interviews.trycloudflare.com', '.trycloudflare.com'],
        proxy: {
            '/blackjack/api': {
                target: 'http://127.0.0.1:8000',
                rewrite: (path) => path.replace(/^\/blackjack/, ''),
                changeOrigin: true,
            },
        },
    },
});