import type { TelemetryPoint, Metrics } from '../entities/telemetry/model';
import type { RobotEvent } from '../entities/issue/model';
export function point(timestamp_ms: number, patch: Partial<TelemetryPoint> = {}): TelemetryPoint {
  return {
    timestamp_ms,
    status: 'OK',
    status_message: null,
    pose: { x: timestamp_ms / 1000, y: 1, yaw: 0.1 },
    cmd_vel: { linear_x: 0.8, angular_z: 0.1 },
    odom_vel: { linear_x: 0.7, angular_z: 0.08 },
    ...patch,
  };
}
export const event: RobotEvent = {
  type: 'NOTF',
  start_ms: 1000,
  end_ms: 2000,
  duration_s: 1,
  samples: 5,
  message: 'TF missing',
};
export function metrics(robotId = 'robot-01'): Metrics {
  return {
    robot_id: robotId,
    from_ms: 0,
    to_ms: Date.now(),
    samples: 30,
    duration_s: 30,
    status_counts: { OK: 28, NOTF: 2 },
    tf_availability: 0.93,
    distance_m: 12,
    displacement_m: 9,
    path_efficiency: 0.75,
    total_rotation_rad: 1,
    avg_speed_mps: 0.7,
    max_speed_mps: 0.9,
    path_speed_mps: 0.4,
    avg_angular_speed_rps: 0.1,
    idle_ratio: 0.1,
    moving_ratio: 0.9,
    linear_tracking: { rmse: 0.1, mae: 0.08, max_abs: 0.2 },
    angular_tracking: { rmse: 0.03, mae: 0.02, max_abs: 0.1 },
    gaps: 1,
    gap_time_s: 2,
  };
}
