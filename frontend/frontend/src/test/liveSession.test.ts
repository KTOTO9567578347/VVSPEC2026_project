import { beforeAll, afterAll, afterEach, describe, it, expect, vi } from 'vitest';
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import {
  LiveSession,
  type LiveState,
  emptyLiveState,
} from '../features/live-telemetry/LiveSession';
import { ObservatoryDatabase } from '../db/database';
import { TelemetryRepository } from '../db/telemetryRepository';
import { settings } from '../config/constants';
import { point } from './fixtures';
import { waitFor } from '@testing-library/react';
class Socket {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  open() {
    this.onopen?.();
  }
  close() {
    this.onclose?.();
  }
  sendPoints(points: ReturnType<typeof point>[], robot_id = 'r') {
    this.onmessage?.({ data: JSON.stringify({ robot_id, points }) });
  }
}
const server = setupServer();
const sessions: LiveSession[] = [];
const databases: ObservatoryDatabase[] = [];
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(async () => {
  sessions.splice(0).forEach((s) => s.stop());
  server.resetHandlers();
  vi.restoreAllMocks();
  for (const db of databases.splice(0)) await db.delete();
});
function create() {
  const db = new ObservatoryDatabase('live-' + crypto.randomUUID());
  databases.push(db);
  const repo = new TelemetryRepository(db);
  const sockets: Socket[] = [];
  let state: LiveState = emptyLiveState();
  const session = new LiveSession({
    robotId: 'r',
    windowS: 600,
    repository: repo,
    onChange: (s) => {
      state = s;
    },
    socketFactory: () => {
      const socket = new Socket();
      sockets.push(socket);
      return socket as unknown as WebSocket;
    },
  });
  sessions.push(session);
  return {
    session,
    repo,
    sockets,
    get state() {
      return state;
    },
  };
}
describe('REST + websocket recovery', () => {
  it('uses the last confirmed point rather than wall time when a batch is committed late', async () => {
    const base = Date.now() - 10000;
    let values = [point(base)];
    const starts: number[] = [];
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', ({ request }) => {
        const from = Number(new URL(request.url).searchParams.get('from_ms'));
        starts.push(from);
        const points = values.filter((p) => p.timestamp_ms >= from);
        return HttpResponse.json({
          robot_id: 'r',
          from_ms: from,
          to_ms: Date.now(),
          total_in_range: points.length,
          stride: 1,
          points,
        });
      }),
    );
    const run = create();
    await run.session.start();
    values = [...values, point(base + 1000)];
    run.sockets[0].open();
    await waitFor(() => expect(run.state.points).toHaveLength(2));
    expect(starts.at(-1)).toBe(base);
  });
  it('recovers missed points after disconnect, handles REST/socket races, and deduplicates', async () => {
    const base = Date.now() - 10000;
    let values = [point(base), point(base + 1000)];
    const requests: number[] = [];
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', async ({ request }) => {
        const from = Number(new URL(request.url).searchParams.get('from_ms'));
        requests.push(from);
        const result = values.filter((p) => p.timestamp_ms >= from);
        await delay(10);
        return HttpResponse.json({
          robot_id: 'r',
          from_ms: from,
          to_ms: Date.now(),
          total_in_range: result.length,
          stride: 1,
          points: result,
        });
      }),
    );
    const run = create();
    await run.session.start();
    run.sockets[0].open();
    await waitFor(() => expect(run.state.syncing).toBe(false));
    run.sockets[0].close();
    expect(run.state.points.map((p) => p.timestamp_ms)).toEqual([base, base + 1000]);
    // New points appeared while disconnected (timestamps are after the last successful REST).
    const missed = Date.now() + 2;
    values = [...values, point(missed), point(missed + 1)];
    await waitFor(() => expect(run.sockets).toHaveLength(2), { timeout: 2500 });
    run.sockets[1].open();
    run.sockets[1].sendPoints([point(missed + 2), point(missed + 1), point(missed + 2)]);
    await waitFor(() =>
      expect(run.state.points.map((p) => p.timestamp_ms)).toEqual([
        base,
        base + 1000,
        missed,
        missed + 1,
        missed + 2,
      ]),
    );
    await waitFor(() => expect(run.state.syncing).toBe(false));
    expect(requests.length).toBeGreaterThanOrEqual(3);
    expect(requests.at(-1)).toBeLessThanOrEqual(missed);
    await waitFor(async () => expect(await run.repo.load('r')).toHaveLength(5));
  });
  it('catches points arriving between initial history and opening the socket', async () => {
    const before = Date.now() - 100;
    let calls = 0;
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', ({ request }) => {
        const from = Number(new URL(request.url).searchParams.get('from_ms'));
        const values = calls++ === 0 ? [point(before)] : [point(Date.now())];
        return HttpResponse.json({
          robot_id: 'r',
          from_ms: from,
          to_ms: Date.now(),
          total_in_range: values.length,
          stride: 1,
          points: values,
        });
      }),
    );
    const run = create();
    await run.session.start();
    expect(run.state.points).toHaveLength(1);
    run.sockets[0].open();
    await waitFor(() => expect(run.state.points).toHaveLength(2));
  });
  it('warns about downsampling, ignores other robots, and tolerates invalid websocket frames', async () => {
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', () =>
        HttpResponse.json({
          robot_id: 'r',
          from_ms: 0,
          to_ms: Date.now(),
          total_in_range: 10,
          stride: 2,
          points: [point(1)],
        }),
      ),
    );
    const run = create();
    await run.session.start();
    run.sockets[0].open();
    run.sockets[0].sendPoints([point(3)], 'other');
    expect(run.state.points).toHaveLength(1);
    run.sockets[0].onmessage?.({ data: 'not-json' });
    expect(run.state.error).toContain('некорректное');
    expect(run.state.sampled).toBe(true);
    run.sockets[0].sendPoints([point(2, { pose: null, status: 'NOTF' })]);
    await waitFor(() => expect(run.state.points.at(-1)?.pose).toBeNull());
  });
  it('does not advance durable recovery watermark if persistence fails', async () => {
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', () =>
        HttpResponse.json({
          robot_id: 'r',
          from_ms: 0,
          to_ms: Date.now(),
          total_in_range: 1,
          stride: 1,
          points: [point(1)],
        }),
      ),
    );
    const run = create();
    vi.spyOn(run.repo, 'save').mockRejectedValue(new Error('Quota'));
    const mark = vi.spyOn(run.repo, 'markSynced');
    await run.session.start();
    expect(mark).not.toHaveBeenCalled();
    expect(run.state.storageError).toContain('IndexedDB');
    expect(run.state.points).toHaveLength(1);
  });
  it('retries failed REST catch-up without waiting for another disconnect', async () => {
    let fail = false;
    let from: number | undefined;
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', ({ request }) => {
        from = Number(new URL(request.url).searchParams.get('from_ms'));
        return fail
          ? new HttpResponse(null, { status: 500 })
          : HttpResponse.json({
              robot_id: 'r',
              from_ms: from,
              to_ms: Date.now(),
              total_in_range: 1,
              stride: 1,
              points: [point(Date.now())],
            });
      }),
    );
    const run = create();
    await run.session.start();
    fail = true;
    run.sockets[0].open();
    await waitFor(() => expect(run.state.error).toContain('500'));
    const failedFrom = from;
    fail = false;
    await run.session.synchronize();
    expect(from).toBe(failedFrom);
    expect(run.state.error).toBeNull();
  });
  it('cleans subscriptions and timers when selection changes or Strict Mode unmounts', async () => {
    server.use(
      http.get('http://localhost:8000/api/robots/r/telemetry', () =>
        HttpResponse.json({
          robot_id: 'r',
          from_ms: 0,
          to_ms: Date.now(),
          total_in_range: 0,
          stride: 1,
          points: [],
        }),
      ),
    );
    const run = create();
    await run.session.start();
    run.session.stop();
    expect(run.sockets[0].onmessage).toBeNull();
    expect(run.sockets[0].onopen).toBeNull();
    expect(settings.historyLimit).toBeLessThanOrEqual(50000);
  });
});
