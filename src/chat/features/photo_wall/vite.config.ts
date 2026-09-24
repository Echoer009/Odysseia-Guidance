import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
    base: '/photo/',
    publicDir: 'public',
    plugins: [vue()],
    envDir: '../../../../',
    server: {
        host: true,
        hmr: false,
        proxy: {
            '/photo/api': {
                target: 'http://127.0.0.1:8006',
                rewrite: (path) => path.replace(/^\/photo/, ''),
                changeOrigin: true,
            },
            '/photo/assets': {
                target: 'http://127.0.0.1:8006',
                rewrite: (path) => path.replace(/^\/photo/, ''),
                changeOrigin: true,
            },
        },
    },
});
