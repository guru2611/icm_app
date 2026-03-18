import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/investigate': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/slack': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/employee': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/dispute-predictor': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/audit-log': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
