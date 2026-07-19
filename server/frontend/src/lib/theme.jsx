import { createContext, useCallback, useContext, useEffect, useState } from 'react';

/*
 * Theme controller. Mirrors the canonical federation ThemeProvider
 * (@pr-federation/react) but is vendored locally so this app builds standalone
 * and offline. Writes BOTH signals so the styling layers agree:
 *   - `.dark` class on <html>   → Tailwind darkMode:["class"]
 *   - `data-theme="dark|light"` → shared federation.css tokens
 * Preference: stored value → OS preference → dark (this app's historical default).
 */
const STORAGE_KEY = 'fd-theme:thehub-pr';
const ThemeContext = createContext(null);

function getInitialTheme() {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    root.dataset.theme = theme;
    try { window.localStorage.setItem(STORAGE_KEY, theme); } catch { /* private mode */ }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within a ThemeProvider');
  return context;
}
