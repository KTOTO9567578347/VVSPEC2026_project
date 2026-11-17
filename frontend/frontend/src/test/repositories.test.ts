import { afterEach, describe, expect, it } from 'vitest';
import { ObservatoryDatabase } from '../db/database';
import { TelemetryRepository } from '../db/telemetryRepository';
import { DexieIssueStatusRepository } from '../db/issueStatusRepository';
import { point, event } from './fixtures';
const databases: ObservatoryDatabase[] = [];
function database() {
  const db = new ObservatoryDatabase('test-' + crypto.randomUUID());
  databases.push(db);
  return db;
}
afterEach(async () => {
  for (const db of databases.splice(0)) await db.delete();
});
describe('durable repositories', () => {
  it('bounds history per robot and atomically stores the latest timestamp', async () => {
    const db = database();
    const repo = new TelemetryRepository(db, 3);
    await repo.save('a', [point(3), point(1), point(2), point(4)], false);
    await repo.save('b', [point(1)], false);
    expect((await repo.load('a')).map((p) => p.timestamp_ms)).toEqual([2, 3, 4]);
    expect(await repo.load('b')).toHaveLength(1);
    expect((await repo.cursor('a'))?.lastTimestamp).toBe(4);
    await repo.markSynced('a', 4);
    await repo.save('a', [point(5)], true);
    expect(await repo.cursor('a')).toMatchObject({
      lastTimestamp: 5,
      syncedThrough: 4,
      sampled: true,
    });
  });
  it('restores a closed event after repeated synchronization and repository recreation', async () => {
    const db = database();
    const repo = new DexieIssueStatusRepository(db);
    const [issue] = await repo.sync('a', [event, event]);
    await repo.setResolved(issue.id, true);
    const again = new DexieIssueStatusRepository(db);
    const rows = await again.sync('a', [event]);
    expect(rows).toHaveLength(1);
    expect(rows[0].resolved).toBe(true);
    expect(rows[0].resolvedAt).toEqual(expect.any(Number));
    await again.setResolved(issue.id, false);
    expect((await again.getAll('a'))[0].resolvedAt).toBeNull();
    await again.sync('a', []);
    expect(await again.getAll('a')).toHaveLength(1);
  });
  it('does not collide between robots or change an existing status on a new event', async () => {
    const repo = new DexieIssueStatusRepository(database());
    const [a] = await repo.sync('a', [event]);
    await repo.setResolved(a.id, true);
    const b = await repo.sync('b', [event]);
    expect(b[0].resolved).toBe(false);
    expect(await repo.sync('a', [{ ...event, start_ms: 10 }])).toHaveLength(2);
  });
  it('reports an unknown issue instead of silently pretending to persist', async () => {
    await expect(
      new DexieIssueStatusRepository(database()).setResolved('unknown', true),
    ).rejects.toThrow();
  });
});
