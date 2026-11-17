import Dexie, { type Table } from 'dexie';
import type { TelemetryPoint } from '../entities/telemetry/model';
import type { Issue } from '../entities/issue/model';
export interface StoredPoint extends TelemetryPoint {
  robotId: string;
}
export interface Cursor {
  robotId: string;
  lastTimestamp: number;
  sampled: boolean;
  syncedThrough?: number;
}
export interface Preference {
  key: string;
  value: string;
}
export interface Snapshot {
  key: string;
  value: unknown;
  savedAt: number;
}
export class ObservatoryDatabase extends Dexie {
  points!: Table<StoredPoint, [string, number]>;
  cursors!: Table<Cursor, string>;
  issues!: Table<Issue, string>;
  preferences!: Table<Preference, string>;
  snapshots!: Table<Snapshot, string>;
  constructor(name = 'vvspec-observatory') {
    super(name);
    this.version(1).stores({
      points: '[robotId+timestamp_ms],robotId',
      cursors: 'robotId',
      issues: 'id,robotId',
      preferences: 'key',
      snapshots: 'key',
    });
  }
}
export const db = new ObservatoryDatabase();
