import Dexie from 'dexie';
import { db, type ObservatoryDatabase } from './database';
import { settings } from '../config/constants';
import type { TelemetryPoint } from '../entities/telemetry/model';
import { mergeTelemetryPoints } from '../entities/telemetry/mergeTelemetryPoints';
export class TelemetryRepository {
  constructor(
    private database: ObservatoryDatabase = db,
    private limit = settings.historyLimit,
  ) {}
  async load(robotId: string) {
    return this.database.points
      .where('[robotId+timestamp_ms]')
      .between([robotId, Dexie.minKey], [robotId, Dexie.maxKey])
      .toArray();
  }
  async cursor(robotId: string) {
    return this.database.cursors.get(robotId);
  }
  async save(robotId: string, incoming: TelemetryPoint[], sampled: boolean) {
    await this.database.transaction('rw', this.database.points, this.database.cursors, async () => {
      const points = mergeTelemetryPoints([], incoming, this.limit);
      await this.database.points.bulkPut(points.map((p) => ({ ...p, robotId })));
      const collection = this.database.points
        .where('[robotId+timestamp_ms]')
        .between([robotId, Dexie.minKey], [robotId, Dexie.maxKey]);
      const overflow = (await collection.count()) - this.limit;
      if (overflow > 0) await collection.limit(overflow).delete();
      const last = await collection.last();
      const previous = await this.database.cursors.get(robotId);
      if (last)
        await this.database.cursors.put({
          ...previous,
          robotId,
          lastTimestamp: last.timestamp_ms,
          sampled: sampled || previous?.sampled === true,
        });
    });
  }
  async markSynced(robotId: string, syncedThrough: number) {
    await this.database.transaction('rw', this.database.cursors, async () => {
      const old = await this.database.cursors.get(robotId);
      await this.database.cursors.put({
        ...old,
        robotId,
        lastTimestamp: old?.lastTimestamp ?? 0,
        sampled: old?.sampled ?? false,
        syncedThrough,
      });
    });
  }
}
export const telemetryRepository = new TelemetryRepository();
