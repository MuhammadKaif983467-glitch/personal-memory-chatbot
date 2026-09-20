/**
 * Typed error classification for frontend error handling.
 * Maps HTTP status codes and network errors to user-friendly categories.
 */

export type ErrorCategory =
  | 'NETWORK_ERROR'
  | 'BACKEND_UNAVAILABLE'
  | 'REQUEST_TIMEOUT'
  | 'ABORTED'
  | 'VALIDATION_ERROR'
  | 'AUTH_ERROR'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'RATE_LIMITED'
  | 'SERVER_ERROR'
  | 'PROVIDER_ERROR'
  | 'UNKNOWN'

export interface ClassifiedError {
  category: ErrorCategory
  message: string
  retryable: boolean
  status: number
  details?: unknown
}

export function classifyHttpError(status: number, message: string, details?: unknown): ClassifiedError {
  if (status === 400) {
    return { category: 'VALIDATION_ERROR', message, retryable: false, status, details }
  }
  if (status === 401 || status === 403) {
    return { category: status === 401 ? 'AUTH_ERROR' : 'FORBIDDEN', message, retryable: false, status, details }
  }
  if (status === 404) {
    return { category: 'NOT_FOUND', message, retryable: false, status, details }
  }
  if (status === 409) {
    return { category: 'CONFLICT', message, retryable: false, status, details }
  }
  if (status === 429) {
    return { category: 'RATE_LIMITED', message, retryable: true, status, details }
  }
  if (status >= 500) {
    return { category: 'SERVER_ERROR', message, retryable: true, status, details }
  }
  return { category: 'UNKNOWN', message, retryable: false, status, details }
}

export function classifyNetworkError(err: Error): ClassifiedError {
  if (err.name === 'AbortError') {
    return {
      category: 'REQUEST_TIMEOUT',
      message: 'The request took too long. Check your connection and try again.',
      retryable: true,
      status: 0,
    }
  }
  return {
    category: 'NETWORK_ERROR',
    message: 'Could not reach the server. Check that the backend is running.',
    retryable: true,
    status: 0,
  }
}

/** User-friendly display text for each error category. */
export const ERROR_DISPLAY: Record<ErrorCategory, string> = {
  NETWORK_ERROR: 'Could not reach the server.',
  BACKEND_UNAVAILABLE: 'The backend is not available.',
  REQUEST_TIMEOUT: 'The request timed out.',
  ABORTED: 'The request was cancelled.',
  VALIDATION_ERROR: 'The request was invalid.',
  AUTH_ERROR: 'Authentication required.',
  FORBIDDEN: 'You do not have access.',
  NOT_FOUND: 'The item was not found.',
  CONFLICT: 'A conflict occurred.',
  RATE_LIMITED: 'Too many requests. Please wait.',
  SERVER_ERROR: 'The server encountered an error.',
  PROVIDER_ERROR: 'The AI provider is temporarily unavailable.',
  UNKNOWN: 'An unexpected error occurred.',
}
