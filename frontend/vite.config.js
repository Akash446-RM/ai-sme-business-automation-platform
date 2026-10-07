import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    // Recharts is large and only used on chart-heavy screens, so keep it in
    // its own chunk instead of inflating the initial bundle.
    rolldownOptions: {
      output: {
        advancedChunks: {
          groups: [
            { name: 'charts', test: /node_modules[\\/](recharts|d3-|victory)/ },
            { name: 'react-vendor', test: /node_modules[\\/](react|react-dom|react-router)/ },
          ],
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
});
