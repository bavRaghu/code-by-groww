const BASE_URL = import.meta.env.VITE_API_BASE || '';
const TOKEN_KEY = 'smw_auth_token';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearAuthToken();
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }
  return response;
}

async function handleResponse(response) {
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

// ----------------------------------------------------------------------
// Auth Endpoints
// ----------------------------------------------------------------------

export async function loginUser(email, password) {
  const res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse(res);
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function registerUser(email, password, name) {
  const res = await fetch(`${BASE_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  });
  const data = await handleResponse(res);
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function fetchCurrentUser() {
  const res = await authFetch(`${BASE_URL}/api/v1/auth/me`);
  return handleResponse(res);
}

export async function logoutUser() {
  try {
    await authFetch(`${BASE_URL}/api/v1/auth/logout`, { method: 'POST' });
  } finally {
    clearAuthToken();
  }
}

// ----------------------------------------------------------------------
// Watchlist Endpoints
// ----------------------------------------------------------------------

export async function fetchWatchlists() {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists`);
  return handleResponse(res);
}

export async function createWatchlist(name) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return handleResponse(res);
}

export async function deleteWatchlist(id) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${id}`, {
    method: 'DELETE',
  });
  return handleResponse(res);
}

export async function fetchWatchlistMarket(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/market`);
  return handleResponse(res);
}

export async function searchInstruments(query = '') {
  const url = query
    ? `${BASE_URL}/api/v1/instruments?search=${encodeURIComponent(query)}`
    : `${BASE_URL}/api/v1/instruments`;
  const res = await authFetch(url);
  return handleResponse(res);
}

export async function addInstrumentToWatchlist(watchlistId, instrumentId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instrument_id: instrumentId }),
  });
  return handleResponse(res);
}

export async function removeInstrumentFromWatchlist(watchlistId, instrumentId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/items/${instrumentId}`, {
    method: 'DELETE',
  });
  return handleResponse(res);
}

export async function checkWatchlist(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/check`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function fetchWatchlistChanges(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/changes`);
  return handleResponse(res);
}

export async function fetchWatchlistAttention(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/attention`);
  return handleResponse(res);
}

export async function refreshWatchlistMarket(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/refresh`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function reviewChange(watchlistId, changeId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/changes/${changeId}/review`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function reviewInstrumentChanges(watchlistId, instrumentId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/instruments/${instrumentId}/review`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function reviewAllWatchlistChanges(watchlistId) {
  const res = await authFetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/review-all`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function fetchStockDetail(instrumentId, watchlistId = null) {
  const url = watchlistId
    ? `${BASE_URL}/api/v1/instruments/${instrumentId}?watchlist_id=${watchlistId}`
    : `${BASE_URL}/api/v1/instruments/${instrumentId}`;
  const res = await authFetch(url);
  return handleResponse(res);
}
