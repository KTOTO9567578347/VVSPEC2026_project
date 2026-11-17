import { useMemo } from 'react';
import type { Robot } from '../../entities/robot/model';
import { useRobotData } from '../../features/live-telemetry/useRobotData';
import { Header } from '../../widgets/header/Header';
import { TrajectoryMap } from '../../widgets/trajectory-map/TrajectoryMap';
import { MotionPanel } from '../../widgets/motion-panel/MotionPanel';
import { MetricsSummary } from '../../widgets/metrics-summary/MetricsSummary';
import { TelemetryCharts } from '../../widgets/telemetry-charts/TelemetryCharts';
import { IssuesPanel } from '../../widgets/issues-panel/IssuesPanel';
import { lastKnownPose } from '../../entities/telemetry/mergeTelemetryPoints';
import { ru } from '../../shared/lib/ru';
import { settings } from '../../config/constants';
import type { ResourceStatus } from '../../shared/ui/ResourceState';
import type { TrajectoryPoint } from '../../entities/telemetry/model';
interface QueryState {
  isPending: boolean;
  isFetching: boolean;
  error: Error | null;
  dataUpdatedAt: number;
}
function status(q: QueryState): ResourceStatus {
  return {
    loading: q.isPending,
    error: q.error,
    refreshing: q.isFetching,
    stale: !!q.dataUpdatedAt && Date.now() - q.dataUpdatedAt > settings.pollMs * 2,
  };
}
interface Props {
  robotId: string;
  robots: Robot[];
  onSelect: (id: string) => void;
  onTheme: () => void;
  windowS: number;
  onWindow: (value: string) => void;
  robotsStale: boolean;
}
export function Dashboard({
  robotId,
  robots,
  onSelect,
  onTheme,
  windowS,
  onWindow,
  robotsStale,
}: Props) {
  const data = useRobotData(robotId, windowS);
  const { live } = data;
  const points = useMemo(() => {
    const from = Date.now() - windowS * 1000;
    return live.points.filter((p) => p.timestamp_ms >= from);
  }, [live.points, windowS]);
  const mapPoints = useMemo(() => {
    const byTime = new Map<number, TrajectoryPoint>();
    const from = Date.now() - windowS * 1000;
    for (const p of data.trajectory.data?.points ?? []) if (p.t >= from) byTime.set(p.t, p);
    for (const p of points)
      if (p.pose) byTime.set(p.timestamp_ms, { t: p.timestamp_ms, ...p.pose });
    return [...byTime.values()].sort((a, b) => a.t - b.t).slice(-settings.historyLimit);
  }, [data.trajectory.data, points, windowS]);
  const latest =
    live.points.at(-1) ?? robots.find((robot) => robot.id === robotId)?.last_point ?? undefined;
  const pose = lastKnownPose(live.points) ?? latest?.pose ?? mapPoints.at(-1) ?? null;
  const telemetryStatus = {
    loading: live.loading && !points.length,
    error: live.error,
    refreshing: live.syncing,
    stale: !!latest && Date.now() - latest.timestamp_ms > settings.staleMs,
  };
  const storageError =
    live.storageError ??
    data.metrics.storageError ??
    data.trajectory.storageError ??
    data.timeseries.storageError ??
    data.events.storageError;
  return (
    <>
      <Header
        robots={robots}
        robotId={robotId}
        onSelect={onSelect}
        onTheme={onTheme}
        live={live}
        onRefresh={data.refresh}
        robotsStale={robotsStale}
      />
      <main className="dashboard">
        <div className="page-heading">
          <div>
            <span className="eyebrow">
              {ru.monitoring.toUpperCase()} / {robotId}
            </span>
            <h1>{ru.overview}</h1>
            <p>{ru.subtitle}</p>
          </div>
          <div className="period-control">
            <span className="live-label">
              <i />
              {ru.live}
            </span>
            <label>
              {ru.period}
              <select value={windowS} onChange={(e) => onWindow(e.target.value)}>
                {!ru.windows.some((w) => w.value === windowS) && (
                  <option value={windowS}>
                    {windowS} {ru.second}
                  </option>
                )}
                {ru.windows.map((w) => (
                  <option key={w.value} value={w.value}>
                    {w.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {storageError && (
          <p className="notice error" role="alert">
            {storageError}
          </p>
        )}
        {live.sampled && <p className="notice warning">{ru.sampled}</p>}
        <div className="primary-grid">
          <TrajectoryMap
            points={mapPoints}
            pose={pose}
            lostPose={!!latest && !latest.pose}
            {...status(data.trajectory)}
            loading={live.loading && !mapPoints.length}
            error={live.error ?? data.trajectory.error}
          />
          <MotionPanel point={latest} pose={pose} {...telemetryStatus} />
        </div>
        <MetricsSummary metrics={data.metrics.data} {...status(data.metrics)} />
        <TelemetryCharts
          points={points}
          timeseries={data.timeseries.data}
          telemetryStatus={telemetryStatus}
          metricsStatus={status(data.timeseries)}
        />
        <IssuesPanel robotId={robotId} events={data.events.data?.events} {...status(data.events)} />
        <footer className="dashboard-footer">
          <span>
            {ru.app} / {ru.product}
          </span>
          <span>
            {ru.retained}: {live.points.length.toLocaleString('ru-RU')} · {ru.pointsLimit}:{' '}
            {settings.historyLimit.toLocaleString('ru-RU')}
          </span>
        </footer>
      </main>
    </>
  );
}
