import type { z } from 'zod';
import { db } from './database';
export const snapshotRepository = {
  async read<T>(key: string, schema: z.ZodType<T>) {
    const row = await db.snapshots.get(key);
    const result = schema.safeParse(row?.value);
    return row && result.success ? { data: result.data, savedAt: row.savedAt } : null;
  },
  async write(key: string, value: unknown) {
    await db.snapshots.put({ key, value, savedAt: Date.now() });
  },
};
