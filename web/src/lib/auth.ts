import { ApiError, apiPost } from './api';

export interface LoginResult {
  ok: boolean;
  error?: string;
}

export async function login(token: string): Promise<LoginResult> {
  try {
    await apiPost<void>('/login', { token });
    return { ok: true };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      return { ok: false, error: 'Invalid token.' };
    }
    return { ok: false, error: e instanceof Error ? e.message : 'Login failed.' };
  }
}

export async function logout(): Promise<void> {
  try { await apiPost<void>('/logout'); } catch { /* ignore */ }
  window.location.assign('/login');
}
