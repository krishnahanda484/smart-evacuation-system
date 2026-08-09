/**
 * Custom fetch configuration for the API client.
 * Wraps the native fetch to direct requests to the backend API.
 */

// The backend API base URL — defaults to same origin for local dev (proxied via Vite)
const API_BASE_URL = (import.meta as any).env?.VITE_API_URL ?? '';

export type ErrorType<T> = T;
export type BodyType<T> = T;

export const customFetch = async <T>(
  url: string,
  options?: RequestInit,
): Promise<T> => {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw error;
  }

  // Handle empty responses
  const text = await response.text();
  return text ? JSON.parse(text) : ({} as T);
};
