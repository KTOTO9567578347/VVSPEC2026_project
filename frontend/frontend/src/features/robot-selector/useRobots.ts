import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { robotsApi } from '../../api/robotsApi';
import { robotSchema } from '../../entities/telemetry/schemas';
import { snapshotRepository } from '../../db/snapshotRepository';
import { settings } from '../../config/constants';
import { ru } from '../../shared/lib/ru';
export function useRobots() {
  const client = useQueryClient();
  const [storageError, setStorageError] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ['robots'],
    queryFn: async ({ signal }) => {
      const data = await robotsApi.list(signal);
      try {
        await snapshotRepository.write('robots', data);
      } catch {
        if (!signal.aborted) setStorageError(ru.storageError);
      }
      return data;
    },
    refetchInterval: settings.pollMs,
  });
  useEffect(() => {
    let active = true;
    void snapshotRepository
      .read('robots', robotSchema.array())
      .then((row) => {
        if (active && row && !client.getQueryData(['robots']))
          client.setQueryData(['robots'], row.data, { updatedAt: row.savedAt });
      })
      .catch(() => {
        if (active) setStorageError(ru.storageError);
      });
    return () => {
      active = false;
    };
  }, [client]);
  return { ...query, storageError };
}
