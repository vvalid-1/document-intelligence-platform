import type { TokenResponse, UserResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

export function login(email: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams({ username: email, password });
  return fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Login failed' })) as { detail?: string };
      throw new Error(body.detail ?? 'Login failed');
    }
    return res.json() as Promise<TokenResponse>;
  });
}

export function register(
  email: string,
  password: string,
  full_name: string,
): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/auth/register', { email, password, full_name });
}

export function getMe(): Promise<UserResponse> {
  return apiGet<UserResponse>('/auth/me');
}

export function logout(): Promise<void> {
  return apiPost<void>('/auth/logout');
}
