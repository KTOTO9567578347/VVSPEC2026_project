import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { z } from 'zod';
import { telemetryApi } from '../../api/telemetryApi';
import { metricsApi } from '../../api/metricsApi';
import { eventsApi } from '../../api/eventsApi';
import {
  trajectorySchema,
  metricsSchema,
  timeseriesSchema,
  eventsSchema,
} from '../../entities/telemetry/schemas';
import { snapshotRepository } from '../../db/snapshotRepository';
import { settings } from '../../config/constants';
import { LiveSession, emptyLiveState } from './LiveSession';
import { ru } from '../../shared/lib/ru';
const range = (windowS: number) => {
  const to = Date.now();
  return { from_ms: Math.max(0, to - windowS * 1000), to_ms: to };
};
function useResource<T>(
  robotId: string,
  windowS: number,
  name: string,
  schema: z.ZodType<T>,
  fetcher: (id: string, r: ReturnType<typeof range>, signal?: AbortSignal) => Promise<T>,
) {
  const client = useQueryClient();
  const [storageError, setStorageError] = useState<string | null>(null);
  const key = ['robot', robotId, windowS, name];
  const cacheKey = JSON.stringify(key);
  const result = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) => {
      const data = await fetcher(robotId, range(windowS), signal);
      try {
        await snapshotRepository.write(cacheKey, data);
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
      .read(cacheKey, schema)
      .then((row) => {
        const parsedKey: unknown = JSON.parse(cacheKey);
        if (active && row && Array.isArray(parsedKey) && !client.getQueryData(parsedKey))
          client.setQueryData(parsedKey, row.data, { updatedAt: row.savedAt });
      })
      .catch(() => {
        if (active) setStorageError(ru.storageError);
      });
    return () => {
      active = false;
    };
  }, [cacheKey, schema, client]);
  return { ...result, storageError };
}
export function useRobotData(robotId: string, windowS: number) {
  const client = useQueryClient();
  const session = useRef<LiveSession | null>(null);
  const [live, setLive] = useState(emptyLiveState);
  const trajectory = useResource(
    robotId,
    windowS,
    'trajectory',
    trajectorySchema,
    telemetryApi.trajectory,
  );
  const metrics = useResource(robotId, windowS, 'metrics', metricsSchema, metricsApi.summary);
  const timeseries = useResource(
    robotId,
    windowS,
    'timeseries',
    timeseriesSchema,
    metricsApi.timeseries,
  );
  const events = useResource(robotId, windowS, 'events', eventsSchema, eventsApi.list);
  useEffect(() => {
    const instance = new LiveSession({
      robotId,
      windowS,
      onChange: setLive,
      initialResources: () =>
        Promise.allSettled([
          client.fetchQuery({ queryKey: ['robot', robotId, windowS, 'trajectory'] }),
          client.fetchQuery({ queryKey: ['robot', robotId, windowS, 'metrics'] }),
          client.fetchQuery({ queryKey: ['robot', robotId, windowS, 'timeseries'] }),
          client.fetchQuery({ queryKey: ['robot', robotId, windowS, 'events'] }),
        ]),
    });
    session.current = instance;
    void instance.start();
    return () => {
      instance.stop();
      session.current = null;
    };
  }, [robotId, windowS, client]);
  return {
    live,
    trajectory,
    metrics,
    timeseries,
    events,
    refresh: () => {
      void session.current?.refresh();
      void client.invalidateQueries({ queryKey: ['robot', robotId] });
      void client.invalidateQueries({ queryKey: ['robots'] });
    },
  };
}
