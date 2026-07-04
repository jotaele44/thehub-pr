const isNode = typeof window === 'undefined';

const toSnakeCase = (str) => str.replace(/([A-Z])/g, '_$1').toLowerCase();

const getStorage = () => {
  if (isNode) return { getItem: () => null, setItem: () => {}, removeItem: () => {} };
  return window.localStorage;
};

const getAppParamValue = (paramName, { defaultValue = undefined, removeFromUrl = false } = {}) => {
  if (isNode) return defaultValue ?? null;
  const storage = getStorage();
  const storageKey = `base44_${toSnakeCase(paramName)}`;
  const urlParams = new URLSearchParams(window.location.search);
  const searchParam = urlParams.get(paramName);

  if (removeFromUrl && searchParam) {
    urlParams.delete(paramName);
    const newUrl = `${window.location.pathname}${urlParams.toString() ? `?${urlParams.toString()}` : ''}${window.location.hash}`;
    window.history.replaceState({}, document.title, newUrl);
  }

  if (searchParam) {
    storage.setItem(storageKey, searchParam);
    return searchParam;
  }
  const storedValue = storage.getItem(storageKey);
  if (storedValue) return storedValue;
  if (defaultValue !== undefined && defaultValue !== null) {
    storage.setItem(storageKey, defaultValue);
    return defaultValue;
  }
  return null;
};

const getAppParams = () => {
  const storage = getStorage();
  if (getAppParamValue('clear_access_token') === 'true') {
    storage.removeItem('base44_access_token');
    storage.removeItem('federation_access_token');
    storage.removeItem('access_token');
    storage.removeItem('token');
  }
  return {
    appId: getAppParamValue('app_id', { defaultValue: import.meta.env.VITE_BASE44_APP_ID || 'thehub-pr' }),
    programId: getAppParamValue('program_id', { defaultValue: import.meta.env.VITE_FEDERATION_PROGRAM_ID || 'prog-control' }),
    token: getAppParamValue('access_token', { removeFromUrl: true }),
    fromUrl: getAppParamValue('from_url', { defaultValue: isNode ? '' : window.location.href }),
    functionsVersion: getAppParamValue('functions_version', { defaultValue: import.meta.env.VITE_BASE44_FUNCTIONS_VERSION }),
    appBaseUrl: getAppParamValue('app_base_url', { defaultValue: import.meta.env.VITE_BASE44_APP_BASE_URL }),
    apiBaseUrl: getAppParamValue('api_base_url', { defaultValue: import.meta.env.VITE_API_BASE_URL || '/api' }),
    requireAuth: String(import.meta.env.VITE_REQUIRE_AUTH || '').toLowerCase() === 'true',
  };
};

export const appParams = { ...getAppParams() };
