import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('app params write-token handling', () => {
  beforeEach(() => {
    const storage = () => {
      const values = new Map();
      return {
        clear: () => values.clear(),
        getItem: (key) => values.get(key) ?? null,
        removeItem: (key) => values.delete(key),
        setItem: (key, value) => values.set(key, String(value)),
      };
    };
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: storage(),
    });
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      value: storage(),
    });
    window.history.replaceState({}, '', '/');
  });

  it('strips URL write tokens and retains them only in session storage', async () => {
    window.history.replaceState({}, '', '/?write_token=session-secret');

    vi.resetModules();
    const { appParams } = await import('./app-params');

    expect(appParams.writeToken).toBe('session-secret');
    expect(window.location.search).toBe('');
    expect(window.sessionStorage.getItem('federation_write_token')).toBe('session-secret');
    expect(window.localStorage.getItem('federation_write_token')).toBeNull();
  });

  it('removes credentials persisted by older builds', async () => {
    window.localStorage.setItem('federation_write_token', 'legacy-secret');

    vi.resetModules();
    const { appParams } = await import('./app-params');

    expect(appParams.writeToken).toBeNull();
    expect(window.localStorage.getItem('federation_write_token')).toBeNull();
  });

  it('clears the session-scoped token when requested', async () => {
    window.sessionStorage.setItem('federation_write_token', 'session-secret');
    window.history.replaceState({}, '', '/?clear_write_token=true');

    vi.resetModules();
    const { appParams } = await import('./app-params');

    expect(appParams.writeToken).toBeNull();
    expect(window.sessionStorage.getItem('federation_write_token')).toBeNull();
    expect(window.location.search).toBe('');
  });

  it('strips the access-token clear flag while removing stored access-token aliases', async () => {
    window.localStorage.setItem('federation_access_token', 'legacy-access-token');
    window.localStorage.setItem('access_token', 'legacy-access-token');
    window.localStorage.setItem('token', 'legacy-access-token');
    window.history.replaceState({}, '', '/?clear_access_token=true');

    vi.resetModules();
    const { appParams } = await import('./app-params');

    expect(appParams.token).toBeNull();
    expect(window.localStorage.getItem('federation_access_token')).toBeNull();
    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(window.location.search).toBe('');
  });
});
