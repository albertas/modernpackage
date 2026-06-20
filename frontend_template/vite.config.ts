/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { configDefaults } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/livez': { target: 'http://localhost:8000', changeOrigin: true },
      '/readyz': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  preview: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/livez': { target: 'http://localhost:8000', changeOrigin: true },
      '/readyz': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    coverage: { provider: 'v8' },
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
});
