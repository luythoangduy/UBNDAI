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

/** FastAPI/Pydantic errors put `detail` as a string, or an array of {msg,...} for 422s. Never let a raw object/array hit .toString(). */
function extractErrorMessage(body: { detail?: unknown; error?: unknown }): string {
  const detail = body.detail ?? body.error;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => (typeof item === 'string' ? item : (item as { msg?: string })?.msg))
      .filter((item): item is string => !!item);
    if (messages.length) return messages.join('; ');
  }
  if (detail && typeof detail === 'object' && typeof (detail as { msg?: string }).msg === 'string') {
    return (detail as { msg: string }).msg;
  }
  return 'Yêu cầu thất bại';
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
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
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
    throw new ApiError(extractErrorMessage(body), response.status, body.detail ?? body.error);
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
    throw new ApiError(extractErrorMessage(body) || 'Không thể mở tài liệu', response.status, body.detail);
  }
  return response.blob();
}

export const idempotency = () => crypto.randomUUID();
