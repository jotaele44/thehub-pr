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
      // Canonical design-system source. The package's own "./styles.css" export
      // points at dist/, which only exists after `npm pack` runs prepack — a
      // `file:` dep is symlinked without lifecycle scripts, so that export can't
      // resolve in-repo. Aliasing the canonical CSS directly is what lets the
      // Hub single-source it instead of keeping a copy in sync.
      '@federation-design': path.resolve(__dirname, '../../federation-design'),
    },
  },
  // The canonical CSS lives outside this Vite root, so the dev server needs
  // explicit permission to serve it.
  server: {
    fs: { allow: [path.resolve(__dirname), path.resolve(__dirname, '../../federation-design')] },
  },
  plugins: OFFLINE ? [react(), viteSingleFile()] : [react()],
  build: OFFLINE
    ? { outDir: 'export-standalone', emptyOutDir: true }
    : {},
});
