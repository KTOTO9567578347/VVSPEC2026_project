import { eventsSchema } from '../entities/telemetry/schemas';
import { request, robotPath, query, sameRobot, type TimeRange } from './httpClient';
export const eventsApi = {
  list: async (id: string, range: TimeRange, signal?: AbortSignal) =>
    sameRobot(id, await request(robotPath(id) + '/events' + query(range), eventsSchema, signal)),
};
