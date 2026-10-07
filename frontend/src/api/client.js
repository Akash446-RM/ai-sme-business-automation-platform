import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const TOKEN_KEY = 'sme_access_token';
export const USER_KEY = 'sme_user';

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
});

/** Attach the bearer token to every outgoing request. */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Convert backend error envelopes into a plain message the UI can show,
 * and sign the user out when a token is rejected.
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const payload = error.response?.data?.error;

    if (status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }

    let message = payload?.message || error.message || 'Something went wrong.';
    const fields = payload?.details?.fields;
    if (Array.isArray(fields) && fields.length) {
      message = fields
        .map((item) => (item.field ? `${item.field}: ${item.message}` : item.message))
        .join('; ');
    }

    return Promise.reject({
      message,
      code: payload?.code || 'request_failed',
      details: payload?.details,
      status,
      original: error,
    });
  },
);

export default api;
