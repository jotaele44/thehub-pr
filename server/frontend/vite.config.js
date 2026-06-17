import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

const OFFLINE = process.env.VITE_OFFLINE === '1';

export default defineConfig({
  logLevel: 'error',
  base: OFFLINE ? './' : '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  plugins: OFFLINE ? [react(), viteSingleFile()] : [react()],
  build: OFFLINE
    ? { outDir: 'export-standalone', emptyOutDir: true }
    : {},
});
