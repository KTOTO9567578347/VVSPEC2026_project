import { metricsSchema, timeseriesSchema } from '../entities/telemetry/schemas';
import { request, robotPath, query, sameRobot, type TimeRange } from './httpClient';
export const metricsApi = {
  summary: async (id: string, range: TimeRange, signal?: AbortSignal) =>
    sameRobot(id, await request(robotPath(id) + '/metrics' + query(range), metricsSchema, signal)),
  timeseries: async (id: string, range: TimeRange, signal?: AbortSignal) =>
    sameRobot(
      id,
      await request(
        robotPath(id) +
          '/metrics/timeseries' +
          query(range, {
            bucket_s: Math.max(1, Math.ceil((range.to_ms - range.from_ms) / 100000)),
          }),
        timeseriesSchema,
        signal,
      ),
    ),
};
