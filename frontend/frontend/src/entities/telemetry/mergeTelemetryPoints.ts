import { settings } from '../../config/constants';
import type { TelemetryPoint } from './model';
export function mergeTelemetryPoints(
  current: TelemetryPoint[],
  incoming: TelemetryPoint[],
  limit = settings.historyLimit,
): TelemetryPoint[] {
  const byTime = new Map(current.map((point) => [point.timestamp_ms, point]));
  // Incoming version wins, including duplicate timestamps within the incoming batch.
  for (const point of incoming) byTime.set(point.timestamp_ms, point);
  return [...byTime.values()].sort((a, b) => a.timestamp_ms - b.timestamp_ms).slice(-limit);
}
export function lastKnownPose(points: TelemetryPoint[]) {
  for (let i = points.length - 1; i >= 0; i--) if (points[i].pose) return points[i].pose;
  return null;
}
export function sampleForDisplay<T>(points: T[], limit: number): T[] {
  if (points.length <= limit) return points;
  return Array.from(
    { length: limit },
    (_, i) => points[Math.round((i * (points.length - 1)) / (limit - 1))],
  );
}
