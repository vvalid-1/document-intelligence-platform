import type { TokenResponse, UserResponse } from '@/types/api';
import { apiGet, apiPost } from './client';

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/auth/login', { email, password });
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
