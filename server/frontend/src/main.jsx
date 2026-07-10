import React from 'react'
import ReactDOM from 'react-dom/client'
import App from '@/App.jsx'
import '@/index.css'
import '@/styles/federation.css'

document.documentElement.dataset.repo = 'thehub-pr'
document.documentElement.dataset.theme = 'dark'

ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
