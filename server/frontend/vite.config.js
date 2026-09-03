import fs from 'node:fs';
import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

const OFFLINE = process.env.VITE_OFFLINE === '1';
const CESIUM_SOURCE = path.resolve(__dirname, 'node_modules/cesium/Build/Cesium');
const CESIUM_DIRS = ['Assets', 'ThirdParty', 'Widgets', 'Workers'];

function cesiumRuntimeAssets() {
  let outDir = path.resolve(__dirname, OFFLINE ? 'export-standalone' : 'dist');
  return {
    name: 'cesium-runtime-assets',
    configResolved(config) {
      outDir = path.resolve(__dirname, config.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use('/cesium', (req, res, next) => {
        try {
          const relative = decodeURIComponent(String(req.url || '').split('?', 1)[0]).replace(/^\/+/, '');
          const candidate = path.resolve(CESIUM_SOURCE, relative);
          const root = `${CESIUM_SOURCE}${path.sep}`;
          if (!candidate.startsWith(root) || !fs.existsSync(candidate) || !fs.statSync(candidate).isFile()) return next();
          const ext = path.extname(candidate).toLowerCase();
          const types = { '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.xml': 'application/xml' };
          if (types[ext]) res.setHeader('Content-Type', types[ext]);
          fs.createReadStream(candidate).pipe(res);
        } catch {
          next();
        }
      });
    },
    closeBundle() {
      const targetRoot = path.join(outDir, 'cesium');
      fs.mkdirSync(targetRoot, { recursive: true });
      for (const directory of CESIUM_DIRS) {
        const source = path.join(CESIUM_SOURCE, directory);
        if (!fs.existsSync(source)) throw new Error(`Cesium runtime asset directory missing: ${source}`);
        fs.cpSync(source, path.join(targetRoot, directory), { recursive: true });
      }
    },
  };
}

export default defineConfig({
  logLevel: 'error',
  base: OFFLINE ? './' : '/',
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
      // Canonical design-system source. The package's own "./styles.css" export
      // points at dist/, which only exists after `npm pack` runs prepack — a
      // `file:` dep is symlinked without lifecycle scripts, so that export can't
      // resolve in-repo. Aliasing the canonical CSS directly is what lets the
      // Hub single-source it instead of keeping a copy in sync.
      '@federation-design': path.resolve(import.meta.dirname, '../../federation-design'),
    },
  },
  server: {
    fs: {
      allow: [
        path.resolve(import.meta.dirname),
        path.resolve(import.meta.dirname, '../../federation-design'),
      ],
    },
  },
  plugins: OFFLINE ? [react(), viteSingleFile(), cesiumRuntimeAssets()] : [react(), cesiumRuntimeAssets()],
  build: OFFLINE
    ? { outDir: 'export-standalone', emptyOutDir: true }
    : {},
});
