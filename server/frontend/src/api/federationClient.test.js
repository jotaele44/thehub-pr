import { beforeEach, describe, expect, it, vi } from 'vitest';
import { federation, requireImplementedResponse, setWriteToken } from './federationClient';

const appParams = vi.hoisted(() => ({
  token: null,
  writeToken: null,
  apiBaseUrl: '/api',
}));
vi.mock('@/lib/app-params', () => ({ appParams }));

const jsonResponse = (body = {}) => new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
});

describe('federationClient request contracts', () => {
  beforeEach(() => {
    const localValues = new Map();
    const sessionValues = new Map();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        clear: () => localValues.clear(),
        getItem: (key) => localValues.get(key) ?? null,
        removeItem: (key) => localValues.delete(key),
        setItem: (key, value) => localValues.set(key, String(value)),
      },
    });
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      value: {
        clear: () => sessionValues.clear(),
        getItem: (key) => sessionValues.get(key) ?? null,
        removeItem: (key) => sessionValues.delete(key),
        setItem: (key, value) => sessionValues.set(key, String(value)),
      },
    });
    appParams.token = null;
    appParams.writeToken = null;
    appParams.apiBaseUrl = '/api';
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(jsonResponse())));
  });

  it('uses access tokens before the diagnostic write token', async () => {
    window.localStorage.setItem('federation_access_token', 'access-token');
    setWriteToken('write-token');

    await federation.request('/probe');

    const [, options] = fetch.mock.calls[0];
    expect(options.headers.get('Authorization')).toBe('Bearer access-token');
  });

  it('falls back to the write token and preserves explicit authorization', async () => {
    setWriteToken('write-token');
    await federation.request('/write');
    expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer write-token');

    await federation.request('/explicit', {
      headers: { Authorization: 'Bearer explicit-token' },
    });
    expect(fetch.mock.calls[1][1].headers.get('Authorization')).toBe('Bearer explicit-token');
  });

  it('keeps administrative write tokens in session storage, not persistent local storage', async () => {
    setWriteToken('session-write-token');

    expect(window.sessionStorage.getItem('federation_write_token')).toBe('session-write-token');
    expect(window.localStorage.getItem('federation_write_token')).toBeNull();

    await federation.request('/write');

    expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe(
      `Bearer ${window.sessionStorage.getItem('federation_write_token')}`,
    );
  });

  it('does not reuse a bootstrap write token after the operator clears it', async () => {
    appParams.writeToken = 'bootstrap-token';
    setWriteToken(null);

    await federation.request('/after-clear');

    expect(fetch.mock.calls[0][1].headers.has('Authorization')).toBe(false);
  });

  it('sends preference writes and uploads using their HTTP contracts', async () => {
    const file = new File(['evidence'], 'evidence.csv', { type: 'text/csv' });
    await federation.notifications.setPreferences(
      { all: { channels: ['push'], timing: 'asap' } },
      { push: 'https://push.example/subscription' },
    );
    await federation.integrations.Core.UploadFile({ file });

    expect(fetch.mock.calls[0][0]).toBe('/api/notifications/preferences');
    expect(fetch.mock.calls[0][1]).toEqual(expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        prefs: { all: { channels: ['push'], timing: 'asap' } },
        targets: { push: 'https://push.example/subscription' },
      }),
    }));
    expect(fetch.mock.calls[1][0]).toBe('/api/files/upload');
    expect(fetch.mock.calls[1][1].body).toBeInstanceOf(FormData);
    expect(fetch.mock.calls[1][1].headers.has('Content-Type')).toBe(false);
  });

  it('surfaces FastAPI detail messages', async () => {
    fetch.mockResolvedValueOnce(new Response(
      JSON.stringify({ detail: 'Missing or invalid write token' }),
      { status: 401, statusText: 'Unauthorized', headers: { 'Content-Type': 'application/json' } },
    ));

    await expect(federation.notifications.setPreferences({}, {}))
      .rejects.toThrow('Missing or invalid write token');
  });

  it('rejects diagnostic stubs instead of treating them as successful results', () => {
    expect(() => requireImplementedResponse({
      status: 'not_implemented',
      reason: 'Provider is not configured.',
    }, 'Research')).toThrow('Provider is not configured.');
    expect(() => requireImplementedResponse({ implemented: false }, 'Research'))
      .toThrow('Research is not available in this deployment.');
    expect(requireImplementedResponse({ findings: [] }, 'Research')).toEqual({ findings: [] });
  });
});
