export async function api(path, options = {}) {
  const adminKey = sessionStorage.getItem('bizsu-admin-key');
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(adminKey ? { 'X-Bizsu-Admin-Key': adminKey } : {}), ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item => item.msg).join('; ') : `Request failed (${response.status})`);
  }
  return body;
}

export const number = value => new Intl.NumberFormat('en-SG').format(value ?? 0);
export const percent = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
export const title = value => value?.replaceAll('_', ' ') ?? '';
