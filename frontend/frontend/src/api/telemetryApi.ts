import { pageSchema, pointSchema, trajectorySchema } from '../entities/telemetry/schemas';
import { settings } from '../config/constants';
import { request, robotPath, query, sameRobot, type TimeRange } from './httpClient';
export const telemetryApi = {
  history: async (id: string, range: TimeRange, signal?: AbortSignal) =>
    sameRobot(
      id,
      await request(
        robotPath(id) + '/telemetry' + query(range, { max_points: settings.maxApiPoints }),
        pageSchema,
        signal,
      ),
    ),
  latest: (id: string, signal?: AbortSignal) =>
    request(robotPath(id) + '/telemetry/latest', pointSchema, signal),
  trajectory: async (id: string, range: TimeRange, signal?: AbortSignal) =>
    sameRobot(
      id,
      await request(
        robotPath(id) + '/trajectory' + query(range, { max_points: settings.maxApiPoints }),
        trajectorySchema,
        signal,
      ),
    ),
};
