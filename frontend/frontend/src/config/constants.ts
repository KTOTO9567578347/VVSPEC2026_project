import { env } from './env';
export const settings = {
  historyLimit: env.VITE_TELEMETRY_HISTORY_LIMIT,
  defaultWindow: env.VITE_DEFAULT_WINDOW_SECONDS,
  requestTimeoutMs: 15000,
  pollMs: 15000,
  staleMs: 10000,
  clockMs: 1000,
  uiBatchMs: 200,
  chartPoints: 1000,
  mapPoints: 3000,
  maxApiPoints: 50000,
  retryStepsMs: [1000, 2000, 4000, 8000, 15000, 30000],
  jitter: 0.15,
  socketOpenTimeoutMs: 15000,
  queryGcMs: 300000,
  issuesPageSize: 20,
};
