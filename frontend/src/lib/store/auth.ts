'use client';

import { create } from 'zustand';

interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  hydrated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  clearAuth: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  hydrated: false,
  setAuth: (token, user) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
      localStorage.setItem('auth_user', JSON.stringify(user));
    }
    set({ token, user });
  },
  clearAuth: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
    }
    set({ token: null, user: null });
  },
  hydrate: () => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('auth_token');
    const userRaw = localStorage.getItem('auth_user');
    let user: AuthUser | null = null;
    if (userRaw) {
      try {
        user = JSON.parse(userRaw) as AuthUser;
      } catch {
        user = null;
      }
    }
    set({ token, user, hydrated: true });
  },
}));
