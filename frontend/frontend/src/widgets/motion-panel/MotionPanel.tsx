import { Navigation } from 'lucide-react';
import type { Pose, TelemetryPoint } from '../../entities/telemetry/model';
import { number } from '../../shared/lib/number';
import { ru } from '../../shared/lib/ru';
import { ResourceState, type ResourceStatus } from '../../shared/ui/ResourceState';
function Speed({
  title,
  unit,
  cmd,
  actual,
}: {
  title: string;
  unit: string;
  cmd: number;
  actual: number;
}) {
  return (
    <div className="speed-block">
      <h3>
        {title}
        <small>{unit}</small>
      </h3>
      <div className="speed-values">
        <div>
          <span>{ru.command}</span>
          <strong>{number(cmd, 3)}</strong>
        </div>
        <div>
          <span>{ru.actual}</span>
          <strong className="accent">{number(actual, 3)}</strong>
        </div>
      </div>
      <div className="speed-delta">
        {ru.delta}
        <span>
          {number(cmd - actual, 3)} {unit}
        </span>
      </div>
    </div>
  );
}
export function MotionPanel({
  point,
  pose,
  ...status
}: ResourceStatus & { point: TelemetryPoint | undefined; pose: Pose | null }) {
  return (
    <section className="panel motion-panel">
      <div className="panel-heading">
        <h2>{ru.motion}</h2>
        <Navigation size={18} />
      </div>
      <ResourceState {...status} empty={!point}>
        {point && (
          <>
            <div className="motion-status">
              <span>{ru.status}</span>
              <span className={'pill ' + (point.status === 'OK' ? 'good' : 'warn')}>
                {point.status}
              </span>
            </div>
            {point.status_message && <p className="notice warning">{point.status_message}</p>}
            <span className="eyebrow">{ru.positionLabel}</span>
            <div className="coordinates">
              {(['x', 'y', 'yaw'] as const).map((k) => (
                <div key={k}>
                  <span>{k.toUpperCase()}</span>
                  <strong>{number(pose?.[k], 3)}</strong>
                  <small>{k === 'yaw' ? ru.rad : ru.meter}</small>
                </div>
              ))}
            </div>
            <Speed
              title={ru.linear}
              unit={ru.speed}
              cmd={point.cmd_vel.linear_x}
              actual={point.odom_vel.linear_x}
            />
            <Speed
              title={ru.angular}
              unit={ru.angularUnit}
              cmd={point.cmd_vel.angular_z}
              actual={point.odom_vel.angular_z}
            />
          </>
        )}
      </ResourceState>
    </section>
  );
}
