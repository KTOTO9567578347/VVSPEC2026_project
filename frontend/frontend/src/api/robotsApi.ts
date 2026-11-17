import { robotSchema } from '../entities/telemetry/schemas';
import { request, robotPath } from './httpClient';
export const robotsApi = {
  list: (signal?: AbortSignal) => request('/api/robots', robotSchema.array(), signal),
  one: (id: string, signal?: AbortSignal) => request(robotPath(id), robotSchema, signal),
};
