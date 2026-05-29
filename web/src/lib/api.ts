// Thin fetch wrapper. Cookies travel automatically (same origin). On 401
// we send the user to /login. All methods return the parsed JSON body
// typed as <T>.

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function buildHeaders(body: unknown, idempotencyKey?: string): HeadersInit {
  const h: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) h['Content-Type'] = 'application/json';
  if (idempotencyKey) h['Idempotency-Key'] = idempotencyKey;
  return h;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  idempotencyKey?: string,
): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: buildHeaders(body, idempotencyKey),
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401 && typeof window !== 'undefined') {
    const here = window.location.pathname;
    if (here !== '/login') window.location.assign('/login');
    throw new ApiError(401, 'unauthorized', null);
  }

  if (res.status === 204) return undefined as unknown as T;

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try { parsed = JSON.parse(text); } catch { parsed = text; }
  }

  if (!res.ok) {
    const message =
      (parsed && typeof parsed === 'object' && 'message' in (parsed as Record<string, unknown>)
        ? String((parsed as Record<string, unknown>).message)
        : null) || res.statusText;
    throw new ApiError(res.status, message, parsed);
  }
  return parsed as T;
}

export const apiGet = <T>(path: string) => request<T>('GET', path);
export const apiPost = <T>(path: string, body?: unknown, idempotencyKey?: string) =>
  request<T>('POST', path, body, idempotencyKey);
export const apiPut = <T>(path: string, body?: unknown) => request<T>('PUT', path, body);
export const apiPatch = <T>(path: string, body?: unknown) => request<T>('PATCH', path, body);
export const apiDelete = (path: string) => request<void>('DELETE', path);
