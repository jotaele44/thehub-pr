import React from 'react'
import ReactDOM from 'react-dom/client'
// Self-hosted fonts (no render-blocking third-party request; offline-safe).
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono'
import App from '@/App.jsx'
import { resolveInitialTheme, applyTheme } from '@/lib/theme'
import '@/index.css'
// Canonical federation layer, imported straight from the design-system source.
// There is no local copy to drift from, so no sync guard is needed.
import '@federation-design/styles/federation.css'

// Repo accent for the shared federation.css.
document.documentElement.dataset.repo = 'thehub-pr'
// Apply the resolved theme synchronously BEFORE the first React render so
// dark-preference users don't see a light first frame flip to dark (no FOUC).
// The ThemeProvider in App.jsx keeps it in sync thereafter.
applyTheme(resolveInitialTheme())

ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
