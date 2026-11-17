// Which theme an application starts in. No React and no DOM, so it can be
// tested directly and called before first paint.
//
// Order: the preference the person saved, then the application's own default,
// then the operating system's preference, then light. A saved preference
// always wins: `defaultTheme` is where a new visitor starts, not a lock. An
// application that wants one theme only passes a single `allowedThemes` entry.
export function resolveFederationTheme({ stored, defaultTheme, prefersDark = false, allowedThemes = ['light', 'dark'] } = {}) {
  const allowed = (value) => typeof value === 'string' && allowedThemes.includes(value)
  if (allowed(stored)) return stored
  if (allowed(defaultTheme)) return defaultTheme
  const system = prefersDark ? 'dark' : 'light'
  if (allowed(system)) return system
  return allowedThemes[0] || 'light'
}
