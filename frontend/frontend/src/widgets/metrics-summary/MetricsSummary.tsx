import { memo } from 'react';
import type { Metrics } from '../../entities/telemetry/model';
import { number, percent } from '../../shared/lib/number';
import { ru } from '../../shared/lib/ru';
import { ResourceState, type ResourceStatus } from '../../shared/ui/ResourceState';
export const MetricsSummary = memo(function MetricsSummary({
  metrics,
  ...status
}: ResourceStatus & { metrics: Metrics | undefined }) {
  const rows = metrics
    ? [
        [ru.points, number(metrics.samples, 0), ''],
        [ru.duration, number(metrics.duration_s, 1), ru.second],
        [ru.tf, percent(metrics.tf_availability), ''],
        [ru.distance, number(metrics.distance_m), ru.meter],
        [ru.displacement, number(metrics.displacement_m), ru.meter],
        [ru.efficiency, percent(metrics.path_efficiency), ''],
        [ru.avgSpeed, number(metrics.avg_speed_mps), ru.speed],
        [ru.maxSpeed, number(metrics.max_speed_mps), ru.speed],
        [ru.idle, percent(metrics.idle_ratio), ''],
        [ru.moving, percent(metrics.moving_ratio), ''],
        [ru.gaps, number(metrics.gaps, 0), ''],
        [ru.gapTime, number(metrics.gap_time_s), ru.second],
      ]
    : [];
  return (
    <section className="metrics-section">
      <div className="section-heading">
        <h2>{ru.metrics}</h2>
        <span>{ru.metricsHint}</span>
      </div>
      <ResourceState {...status} empty={!metrics || metrics.samples === 0}>
        <div className="metrics-grid">
          {rows.map(([label, value, unit]) => (
            <div className="metric-card" key={label}>
              <span>{label}</span>
              <strong>
                {value}
                <small>{unit}</small>
              </strong>
            </div>
          ))}
        </div>
      </ResourceState>
    </section>
  );
});
