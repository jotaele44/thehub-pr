import React from 'react'
import ReactDOM from 'react-dom/client'
// Self-hosted fonts (no render-blocking third-party request; offline-safe).
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono'
import App from '@/App.jsx'
import '@/index.css'
import '@/styles/federation.css'

// Repo accent for the shared federation.css; theme (light/dark) is owned by the
// ThemeProvider in App.jsx, which sets `.dark` + data-theme from stored/OS preference.
document.documentElement.dataset.repo = 'thehub-pr'

ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
