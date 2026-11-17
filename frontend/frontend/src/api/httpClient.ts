import { z } from 'zod';
import { env } from '../config/env';
import { settings } from '../config/constants';
import { ru } from '../shared/lib/ru';
export class ApiError extends Error {
  constructor(
    public kind: 'network' | 'timeout' | 'http' | 'json' | 'validation',
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, settings.requestTimeoutMs);
  try {
    const response = await fetch(env.VITE_API_BASE_URL.replace(/\/$/, '') + path, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = null;
      }
      const noTelemetry =
        detail !== null &&
        typeof detail === 'object' &&
        'detail' in detail &&
        detail.detail === 'no telemetry yet';
      const message =
        response.status === 404
          ? noTelemetry
            ? ru.noTelemetry
            : ru.notFound
          : response.status === 422
            ? ru.queryError
            : (response.status >= 500 ? ru.serverError : ru.httpError) +
              ' (' +
              response.status +
              ')';
      throw new ApiError('http', message, response.status);
    }
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new ApiError('json', ru.json);
    }
    const parsed = schema.safeParse(data);
    if (!parsed.success) throw new ApiError('validation', ru.invalid);
    return parsed.data;
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (timedOut) throw new ApiError('timeout', ru.timeout);
    if (error instanceof ApiError) throw error;
    throw new ApiError('network', ru.network);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}
export interface TimeRange {
  from_ms: number;
  to_ms: number;
}
export function robotPath(id: string) {
  return '/api/robots/' + encodeURIComponent(id);
}
export function query(range: TimeRange, extra: Record<string, number> = {}) {
  return (
    '?' +
    new URLSearchParams(Object.entries({ ...range, ...extra }).map(([k, v]) => [k, String(v)]))
  );
}
export function sameRobot<T extends { robot_id: string }>(id: string, data: T): T {
  if (data.robot_id !== id) throw new ApiError('validation', ru.invalid);
  return data;
}
