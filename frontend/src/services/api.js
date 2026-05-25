const API_BASE = process.env.REACT_APP_API_BASE || 'http://127.0.0.1:5000/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    // no JSON body
  }

  if (!res.ok) {
    // Handle unauthorized centrally
    if (res.status === 401) {
      // clear token and reload to force login
      localStorage.removeItem('token');
      // reload page so user returns to login screen
      window.location.reload();
      throw new Error(data?.message || 'Unauthorized');
    }
    throw new Error(data?.message || `Request failed with status ${res.status}`);
  }

  return data;
}

async function post(path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return request(path, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  });
}

async function get(path, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return request(path, {
    method: 'GET',
    headers
  });
}

async function del(path, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return request(path, {
    method: 'DELETE',
    headers
  });
}

export { post, get, del };
