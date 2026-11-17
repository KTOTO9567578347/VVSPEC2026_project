import { describe, it, expect } from 'vitest';
import { createIssueId } from '../entities/issue/createIssueId';
import { mapEventToIssue } from '../entities/issue/mapEventToIssue';
import {
  mergeTelemetryPoints,
  lastKnownPose,
  sampleForDisplay,
} from '../entities/telemetry/mergeTelemetryPoints';
import { retryDelay } from '../shared/lib/retry';
import { point, event } from './fixtures';
describe('stable event identities', () => {
  it('is deterministic and considers every identity field', () => {
    const id = createIssueId('r', event);
    expect(createIssueId('r', { ...event })).toBe(id);
    for (const change of [
      { type: 'GAP' as const },
      { start_ms: 2 },
      { end_ms: 3 },
      { message: 'new' },
    ])
      expect(createIssueId('r', { ...event, ...change })).not.toBe(id);
    expect(createIssueId('other', event)).not.toBe(id);
    expect(createIssueId('r', { ...event, message: null })).not.toBe(
      createIssueId('r', { ...event, message: '' }),
    );
  });
  it('maps an event and restores only the matching local status', () => {
    const original = mapEventToIssue('r', event);
    expect(original.title).toBe('Потеря координат');
    expect(original.resolved).toBe(false);
    const closed = mapEventToIssue('r', event, { ...original, resolved: true, resolvedAt: 3000 });
    expect(closed.resolvedAt).toBe(3000);
    expect(mapEventToIssue('r', { ...event, end_ms: 5000 }, closed).resolved).toBe(false);
  });
});
describe('telemetry merge', () => {
  it('sorts, deduplicates, lets the incoming version win, and does not mutate', () => {
    const current = [point(3), point(1)];
    const incoming = [point(2), point(1, { status: 'ERROR' })];
    Object.freeze(current);
    Object.freeze(incoming);
    const merged = mergeTelemetryPoints(current, incoming);
    expect(merged.map((p) => p.timestamp_ms)).toEqual([1, 2, 3]);
    expect(merged[0].status).toBe('ERROR');
    expect(current[1].status).toBe('OK');
  });
  it('keeps the newest points within the configured limit', () => {
    expect(
      mergeTelemetryPoints([point(1), point(4)], [point(2), point(3)], 2).map(
        (p) => p.timestamp_ms,
      ),
    ).toEqual([3, 4]);
  });
  it('retains the last pose when coordinates are absent', () => {
    expect(lastKnownPose([point(1), point(2, { pose: null, status: 'NOTF' })])).toEqual(
      point(1).pose,
    );
    expect(lastKnownPose([point(2, { pose: null })])).toBeNull();
  });
  it('samples only presentation data and retains endpoints', () => {
    const input = [1, 2, 3, 4, 5];
    expect(sampleForDisplay(input, 3)).toEqual([1, 3, 5]);
    expect(input).toHaveLength(5);
  });
});
describe('reconnect backoff', () => {
  it('uses increasing intervals and caps at 30 seconds', () => {
    expect([0, 1, 2, 3, 4, 5, 20].map((n) => retryDelay(n, () => 0.5))).toEqual([
      1000, 2000, 4000, 8000, 15000, 30000, 30000,
    ]);
    expect(retryDelay(0, () => 0)).toBe(850);
    expect(retryDelay(5, () => 1)).toBe(30000);
  });
});
