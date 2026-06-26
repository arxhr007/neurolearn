const BASE = 'http://localhost:8000';

async function request(method, path, body, isFormData = false) {
  const token = localStorage.getItem('access_token');
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!isFormData && body) headers['Content-Type'] = 'application/json';

  let res = await fetch(BASE + path, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
      res = await fetch(BASE + path, {
        method,
        headers,
        body: isFormData ? body : body ? JSON.stringify(body) : undefined,
      });
    } else {
      localStorage.clear();
      window.location.href = '/login';
      return;
    }
  }

  const text = await res.text();
  try { return JSON.parse(text); } catch { return text; }
}

async function tryRefresh() {
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) return false;
  try {
    const r = await fetch(`${BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!r.ok) return false;
    const data = await r.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  } catch { return false; }
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
  postForm: (path, fd) => request('POST', path, fd, true),
};
