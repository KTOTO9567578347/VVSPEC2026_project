import { db } from './database';
export const preferencesRepository = {
  async get(key: string) {
    return (await db.preferences.get(key))?.value;
  },
  async set(key: string, value: string) {
    await db.preferences.put({ key, value });
  },
};
