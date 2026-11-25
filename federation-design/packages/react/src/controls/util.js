// Shared by the control components. Kept apart from shell/parts.jsx so the
// shell can import controls without a cycle.
export function cx(...values) {
  return values.filter(Boolean).join(' ')
}
