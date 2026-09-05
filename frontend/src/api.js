const BASE_URL = import.meta.env.VITE_API_BASE || '';

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

export async function fetchWatchlists() {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists`);
  return handleResponse(res);
}

export async function createWatchlist(name) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return handleResponse(res);
}

export async function deleteWatchlist(id) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${id}`, {
    method: 'DELETE',
  });
  return handleResponse(res);
}

export async function fetchWatchlistMarket(watchlistId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/market`);
  return handleResponse(res);
}

export async function searchInstruments(query = '') {
  const url = query
    ? `${BASE_URL}/api/v1/instruments?search=${encodeURIComponent(query)}`
    : `${BASE_URL}/api/v1/instruments`;
  const res = await fetch(url);
  return handleResponse(res);
}

export async function addInstrumentToWatchlist(watchlistId, instrumentId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instrument_id: instrumentId }),
  });
  return handleResponse(res);
}

export async function removeInstrumentFromWatchlist(watchlistId, instrumentId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/items/${instrumentId}`, {
    method: 'DELETE',
  });
  return handleResponse(res);
}

export async function checkWatchlist(watchlistId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/check`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function fetchWatchlistChanges(watchlistId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/changes`);
  return handleResponse(res);
}

export async function fetchWatchlistAttention(watchlistId) {
  const res = await fetch(`${BASE_URL}/api/v1/watchlists/${watchlistId}/attention`);
  return handleResponse(res);
}

