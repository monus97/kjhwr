// Single place that knows where the backend lives.
const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ).toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ''}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `${res.status} ${res.statusText}`);
  return body;
}

export const api = {
  meta: () => get('/api/meta'),
  decision: (deliveryDay, decisionTime) =>
    get('/api/decision', { delivery_day: deliveryDay, decision_time: decisionTime }),
  accuracy: (start, end, horizon) => get('/api/accuracy', { start, end, horizon }),
  horizonCurve: (start, end) => get('/api/horizon-curve', { start, end }),
};
