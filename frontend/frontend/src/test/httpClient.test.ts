import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import { z } from 'zod';
import { request } from '../api/httpClient';
import { telemetryApi } from '../api/telemetryApi';
import { settings } from '../config/constants';
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
const url = 'http://localhost:8000/test';
describe('HTTP boundary', () => {
  it.each([404, 422, 500, 503])('reports HTTP %s', async (status) => {
    server.use(http.get(url, () => HttpResponse.json({ detail: 'robot not found' }, { status })));
    await expect(request('/test', z.object({}))).rejects.toMatchObject({ kind: 'http', status });
  });
  it('distinguishes no telemetry yet', async () => {
    server.use(
      http.get(url, () => HttpResponse.json({ detail: 'no telemetry yet' }, { status: 404 })),
    );
    await expect(request('/test', z.object({}))).rejects.toThrow('Телеметрии пока нет');
  });
  it('rejects invalid JSON', async () => {
    server.use(http.get(url, () => new HttpResponse('not json')));
    await expect(request('/test', z.object({}))).rejects.toMatchObject({ kind: 'json' });
  });
  it('rejects unexpected structures', async () => {
    server.use(http.get(url, () => HttpResponse.json({ wrong: true })));
    await expect(request('/test', z.object({ id: z.string() }))).rejects.toMatchObject({
      kind: 'validation',
    });
  });
  it('reports network or CORS failures without claiming to distinguish them', async () => {
    server.use(http.get(url, () => HttpResponse.error()));
    await expect(request('/test', z.object({}))).rejects.toMatchObject({ kind: 'network' });
  });
  it('supports caller cancellation', async () => {
    server.use(
      http.get(url, async () => {
        await delay(100);
        return HttpResponse.json({});
      }),
    );
    const abort = new AbortController();
    const pending = request('/test', z.object({}), abort.signal);
    abort.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('distinguishes a timeout from a network error', async () => {
    const previous = settings.requestTimeoutMs;
    settings.requestTimeoutMs = 15;
    server.use(
      http.get(url, async () => {
        await delay(50);
        return HttpResponse.json({});
      }),
    );
    try {
      await expect(request('/test', z.object({}))).rejects.toMatchObject({ kind: 'timeout' });
    } finally {
      settings.requestTimeoutMs = previous;
    }
  });
  it('rejects a REST envelope for a different robot', async () => {
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', () =>
        HttpResponse.json({
          robot_id: 'wrong',
          from_ms: 0,
          to_ms: 5,
          total_in_range: 0,
          stride: 1,
          points: [],
        }),
      ),
    );
    await expect(telemetryApi.history('r', { from_ms: 0, to_ms: 5 })).rejects.toMatchObject({
      kind: 'validation',
    });
  });
});
