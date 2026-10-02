import { useEffect } from 'react';

// Ctrl+K (Windows/Linux) or Cmd+K (macOS) anywhere in the app (TWIN-095).
export function isPaletteShortcut(event) {
  return Boolean(event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && String(event.key).toLowerCase() === 'k';
}

export default function useGlobalShortcut(handler) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (!isPaletteShortcut(event)) return;
      event.preventDefault();
      handler();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handler]);
}
