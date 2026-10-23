const isNode = typeof window === 'undefined';
const windowObj = isNode ? {
  localStorage: new Map(),
  sessionStorage: new Map(),
  location: { href: '' },
  history: { replaceState: () => {} },
} : window;
const storage = windowObj.localStorage;
const sessionStorage = windowObj.sessionStorage;

const toSnakeCase = (str) => str.replace(/([A-Z])/g, '_$1').toLowerCase();

const getParamValue = (
  paramName,
  { defaultValue = undefined, removeFromUrl = false, valueStorage = storage } = {},
) => {
  if (isNode) return defaultValue ?? null;
  const storageKey = `federation_${toSnakeCase(paramName)}`;
  const urlParams = new URLSearchParams(window.location.search);
  const searchParam = urlParams.get(paramName);

  if (removeFromUrl) {
    urlParams.delete(paramName);
    const newUrl = `${window.location.pathname}${urlParams.toString() ? `?${urlParams.toString()}` : ''}${window.location.hash}`;
    window.history.replaceState({}, document.title, newUrl);
  }

  if (searchParam) {
    valueStorage.setItem(storageKey, searchParam);
    return searchParam;
  }
  if (defaultValue !== undefined && defaultValue !== null) {
    valueStorage.setItem(storageKey, defaultValue);
    return defaultValue;
  }
  return valueStorage.getItem(storageKey);
};

const getAppParams = () => {
  if (getParamValue('clear_access_token', { removeFromUrl: true }) === 'true') {
    storage.removeItem('federation_access_token');
    storage.removeItem('access_token');
    storage.removeItem('token');
  }
  if (getParamValue('clear_write_token', { removeFromUrl: true }) === 'true') {
    sessionStorage.removeItem('federation_write_token');
    storage.removeItem('federation_write_token');
  }
  // Migrate away from credentials persisted by older builds.
  storage.removeItem('federation_write_token');

  const programId = import.meta.env.VITE_FEDERATION_PROGRAM_ID || 'thehub-pr';
  const scopedApiBaseUrl = import.meta.env.VITE_HUB_API_BASE_URL;

  return {
    appId: getParamValue('app_id', { defaultValue: import.meta.env.VITE_FEDERATION_APP_ID || programId }),
    programId,
    apiBaseUrl: getParamValue('api_base_url', {
      defaultValue: scopedApiBaseUrl || import.meta.env.VITE_FEDERATION_API_BASE_URL || '/api',
    }),
    token: getParamValue('access_token', { removeFromUrl: true }),
    // PRII_WRITE_TOKEN, supplied as ?write_token=… and retained only for this tab session.
    // Deliberately a separate slot from `token`: in diagnostic mode
    // `/api/auth/me` always 401s, and AuthContext responds by clearing the
    // access token so a stale one cannot trap the session in a login redirect
    // (lib/AuthContext.jsx). That cleanup must not wipe the administrative
    // credential. Session storage also avoids persisting it after the tab closes.
    writeToken: getParamValue('write_token', {
      removeFromUrl: true,
      valueStorage: sessionStorage,
    }),
    fromUrl: getParamValue('from_url', { defaultValue: window.location.href }),
    mode: import.meta.env.VITE_FEDERATION_MODE || 'control-plane',
    requireAuth: import.meta.env.VITE_FEDERATION_REQUIRE_AUTH === 'true',
  };
};

export const appParams = {
  ...getAppParams(),
};
