import React from 'react'
import ReactDOM from 'react-dom/client'
// Self-hosted fonts (no render-blocking third-party request; offline-safe).
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono'
import App from '@/App.jsx'
import '@/index.css'
import '@/styles/federation.css'

document.documentElement.dataset.repo = 'thehub-pr'
document.documentElement.dataset.theme = 'dark'

ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
