export type Envelope<T> = { success: boolean; data: T; error?: string };
const citizenTokenKey = 'ubndai.citizen.access_token';
const officerTokenKey = 'ubndai.officer.access_token';
const tokenKeyForPath = () => location.pathname.startsWith('/officer') ? officerTokenKey : citizenTokenKey;

export class ApiError extends Error {
  constructor(message: string, public status: number, public detail?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

export const token = () => localStorage.getItem(tokenKeyForPath()) ?? '';
export const setToken = (value: string, role?: 'citizen' | 'officer') => {
  const key = role === 'officer' ? officerTokenKey : role === 'citizen' ? citizenTokenKey : tokenKeyForPath();
  if (value) localStorage.setItem(key, value);
  else localStorage.removeItem(key);
};

export const clearOfficerSession = () => setToken('', 'officer');

function withHeaders(init: RequestInit) {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const auth = token();
  if (auth) headers.set('Authorization', `Bearer ${auth}`);
  return headers;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: withHeaders(init) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      const role = location.pathname.startsWith('/officer') ? 'officer' : 'citizen';
      setToken('', role);
      window.dispatchEvent(new Event(`${role}-session-expired`));
    }
    throw new ApiError(body.detail ?? body.error ?? 'Yêu cầu thất bại', response.status);
  }
  return (body.data ?? body) as T;
}

export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: withHeaders(init) });
  if (!response.ok) {
    if (response.status === 401) {
      const role = location.pathname.startsWith('/officer') ? 'officer' : 'citizen';
      setToken('', role);
      window.dispatchEvent(new Event(`${role}-session-expired`));
    }
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail : detail?.message ?? 'Không thể mở tài liệu';
    throw new ApiError(message, response.status, detail);
  }
  return response.blob();
}

export const idempotency = () => crypto.randomUUID();
