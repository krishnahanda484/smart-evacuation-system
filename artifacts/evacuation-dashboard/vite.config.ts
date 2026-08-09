import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const port = Number(process.env.PORT) || 5173;

export default defineConfig({
  base: '/',
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '@assets': path.resolve(
        import.meta.dirname,
        '..',
        '..',
        'attached_assets',
      ),
      '@workspace/api-client-react': path.resolve(
        import.meta.dirname,
        '..',
        '..',
        'lib',
        'api-client-react',
        'src',
        'index.ts',
      ),
    },
    dedupe: ['react', 'react-dom', '@tanstack/react-query'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist/public'),
    emptyOutDir: true,
    rollupOptions: {
      // Ensure all external files can resolve their dependencies from this node_modules
    },
  },
  server: {
    port,
    strictPort: false,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
    fs: {
      strict: false,
      // Allow serving files from the entire project (including lib/)
      allow: [
        path.resolve(import.meta.dirname),
        path.resolve(import.meta.dirname, '..', '..', 'lib'),
      ],
    },
  },
  preview: {
    port,
    host: '0.0.0.0',
  },
  optimizeDeps: {
    include: ['@tanstack/react-query'],
    // Force vite to process files outside root
    entries: [
      'src/**/*.{ts,tsx}',
      '../../lib/api-client-react/src/**/*.ts',
    ],
  },
});
