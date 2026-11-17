import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1' },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (/recharts|d3-|victory|decimal|react-smooth|reselect|redux|immer/.test(id))
              return 'charts';
            if (/dexie|zod/.test(id)) return 'data';
            if (/react|scheduler/.test(id)) return 'react';
          }
        },
      },
    },
  },
  test: {
    include: ['src/test/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      include: ['src/entities/**', 'src/features/**', 'src/api/**', 'src/db/**'],
    },
  },
});
