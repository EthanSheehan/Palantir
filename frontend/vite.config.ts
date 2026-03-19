import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@app': path.resolve(__dirname, 'app'),
    },
    dedupe: ['react', 'react-dom'],
  },
  server: {
    port: 8093,
    proxy: {
      '/api/v1': {
        target: 'http://localhost:8012',
        changeOrigin: true,
      },
      '/ws/stream': {
        target: 'ws://localhost:8012',
        ws: true,
      },
      '/ws/events': {
        target: 'ws://localhost:8012',
        ws: true,
      },
    },
  },
});
