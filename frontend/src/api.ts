export type Envelope<T> = { success: boolean; data: T; error?: string };
const citizenTokenKey = 'ubndai.citizen.access_token';
const officerTokenKey = 'ubndai.officer.access_token';
const tokenKeyForPath = () => location.pathname.startsWith('/officer') ? officerTokenKey : citizenTokenKey;
export const token = () => localStorage.getItem(tokenKeyForPath()) ?? '';
export const setToken = (value: string, role?: 'citizen' | 'officer') => {
  localStorage.setItem(role === 'officer' ? officerTokenKey : role === 'citizen' ? citizenTokenKey : tokenKeyForPath(), value);
};
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const auth = token(); if (auth) headers.set('Authorization', `Bearer ${auth}`);
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? body.error ?? 'Yêu cầu thất bại');
  return (body.data ?? body) as T;
}
export const idempotency = () => crypto.randomUUID();
