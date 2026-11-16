import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

const here = new URL('./', import.meta.url)
const exactAlias = (find, relative) => ({ find, replacement: fileURLToPath(new URL(relative, here)) })

export default defineConfig({
  plugins: [react()],
  // Two pages: the component fixtures and the shell fixtures.
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', here)),
        shell: fileURLToPath(new URL('./shell.html', here)),
      },
    },
  },
  resolve: {
    alias: [
      exactAlias(/^@pr-federation\/react$/, '../packages/react/src/index.jsx'),
      exactAlias(/^react-dom\/client$/, './node_modules/react-dom/client.js'),
      exactAlias(/^react-dom$/, './node_modules/react-dom/index.js'),
      exactAlias(/^react$/, './node_modules/react/index.js'),
    ],
    dedupe: ['react', 'react-dom'],
  },
})
