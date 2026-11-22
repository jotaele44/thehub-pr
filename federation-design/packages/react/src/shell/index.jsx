// The federation application shell (FEDERATION_GUI_STANDARD.md §4).
// Named re-exports only, so the public surface is readable here and the API
// snapshot check can see every name.
export { defineFederationNav, flattenFederationNav, matchFederationNavItem } from './nav.js'
export { FederationAppShell } from './AppShell.jsx'
export { FederationModuleNav } from './ModuleNav.jsx'
export { FederationMobileNav } from './MobileNav.jsx'
export { FederationInspectorPanel } from './InspectorPanel.jsx'
export { FederationStatusBar } from './StatusBar.jsx'
