import { memo, useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { MetricsTimeseries, TelemetryPoint } from '../../entities/telemetry/model';
import { sampleForDisplay } from '../../entities/telemetry/mergeTelemetryPoints';
import { settings } from '../../config/constants';
import { number } from '../../shared/lib/number';
import { time } from '../../shared/lib/date';
import { ru } from '../../shared/lib/ru';
import { ResourceState, type ResourceStatus } from '../../shared/ui/ResourceState';
interface Series {
  key: string;
  label: string;
  color: string;
  axis?: string;
}
interface ChartRow {
  t: number;
  [key: string]: number;
}
function Chart({
  title,
  unit,
  rows,
  series,
  ...status
}: ResourceStatus & { title: string; unit: string; rows: ChartRow[]; series: Series[] }) {
  const dual = series.some((s) => s.axis === 'right');
  return (
    <section className="panel chart-panel">
      <div className="panel-heading">
        <h3>{title}</h3>
        <small>{unit}</small>
      </div>
      <ResourceState {...status} empty={!rows.length}>
        <div className="chart" role="img" aria-label={title + ' · ' + unit}>
          <ResponsiveContainer width="100%" height={210} minWidth={0}>
            <LineChart data={rows} margin={{ top: 12, right: dual ? 12 : 20, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="t"
                tickFormatter={time}
                minTickGap={45}
                tick={{ fontSize: 10, fill: 'var(--muted)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="left"
                width={42}
                tickFormatter={(v) => number(Number(v), 2)}
                tick={{ fontSize: 10, fill: 'var(--muted)' }}
                axisLine={false}
                tickLine={false}
              />
              {dual && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  width={42}
                  tickFormatter={(v) => number(Number(v), 2)}
                  tick={{ fontSize: 10, fill: 'var(--muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
              )}
              <Tooltip
                labelFormatter={(v) => time(Number(v))}
                formatter={(v, name) => [number(Number(v), 3), name]}
                contentStyle={{
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} iconType="plainline" />
              {series.map((s) => (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  yAxisId={s.axis ?? 'left'}
                  strokeWidth={2}
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ResourceState>
    </section>
  );
}
export const TelemetryCharts = memo(function TelemetryCharts({
  points,
  timeseries,
  telemetryStatus,
  metricsStatus,
}: {
  points: TelemetryPoint[];
  timeseries: MetricsTimeseries | undefined;
  telemetryStatus: ResourceStatus;
  metricsStatus: ResourceStatus;
}) {
  const rows = useMemo(
    () =>
      sampleForDisplay(points, settings.chartPoints).map((p) => ({
        t: p.timestamp_ms,
        cmd: p.cmd_vel.linear_x,
        actual: p.odom_vel.linear_x,
        cmdAngular: p.cmd_vel.angular_z,
        actualAngular: p.odom_vel.angular_z,
      })),
    [points],
  );
  const buckets = useMemo(
    () =>
      timeseries?.buckets.map((b) => ({
        t: b.t,
        tf: b.tf_availability * 100,
        linear: b.linear_rmse,
        angular: b.angular_rmse,
      })) ?? [],
    [timeseries],
  );
  return (
    <section>
      <div className="section-heading">
        <h2>{ru.charts}</h2>
        <span>{ru.mapSimplified}</span>
      </div>
      <div className="charts-grid">
        <Chart
          title={ru.linear}
          unit={ru.speed}
          rows={rows}
          series={[
            { key: 'cmd', label: ru.command, color: '#a8b9b3' },
            { key: 'actual', label: ru.actual, color: '#268276' },
          ]}
          {...telemetryStatus}
        />
        <Chart
          title={ru.angular}
          unit={ru.angularUnit}
          rows={rows}
          series={[
            { key: 'cmdAngular', label: ru.command, color: '#a8b9b3' },
            { key: 'actualAngular', label: ru.actual, color: '#268276' },
          ]}
          {...telemetryStatus}
        />
        <Chart
          title={ru.tf}
          unit={ru.percent}
          rows={buckets}
          series={[{ key: 'tf', label: ru.tf, color: '#268276' }]}
          {...metricsStatus}
        />
        <Chart
          title={ru.tracking}
          unit={ru.speed + ' / ' + ru.angularUnit}
          rows={buckets}
          series={[
            { key: 'linear', label: ru.linearError, color: '#268276' },
            { key: 'angular', label: ru.angularError, color: '#d29b54', axis: 'right' },
          ]}
          {...metricsStatus}
        />
      </div>
    </section>
  );
});
