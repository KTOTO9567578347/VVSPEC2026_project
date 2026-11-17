import { z } from 'zod';
const n = z.number().finite();
const time = n.int().nonnegative();
export const poseSchema = z.object({ x: n, y: n, yaw: n });
export const twistSchema = z.object({ linear_x: n, angular_z: n });
export const pointSchema = z.object({
  timestamp_ms: time,
  status: z.enum(['OK', 'NOTF', 'ERROR']),
  status_message: z.string().nullable(),
  pose: poseSchema.nullable(),
  cmd_vel: twistSchema,
  odom_vel: twistSchema,
});
export const pageSchema = z.object({
  robot_id: z.string(),
  from_ms: time,
  to_ms: time,
  total_in_range: time,
  stride: n.int().positive(),
  points: z.array(pointSchema),
});
export const trajectoryPointSchema = z.object({ t: time, x: n, y: n, yaw: n });
export const trajectorySchema = z.object({
  robot_id: z.string(),
  from_ms: time,
  to_ms: time,
  points: z.array(trajectoryPointSchema),
});
export const liveSchema = z.object({ robot_id: z.string(), points: z.array(pointSchema) });
export const robotSchema = z.object({
  id: z.string().min(1),
  online: z.boolean(),
  first_seen_ms: time,
  last_seen_ms: time,
  last_point_ms: time.nullable(),
  total_points: time,
  total_batches: time,
  last_point: pointSchema.nullable(),
});
export const eventSchema = z.object({
  type: z.enum(['NOTF', 'ERROR', 'GAP']),
  start_ms: time,
  end_ms: time,
  duration_s: n,
  samples: time,
  message: z.string().nullable(),
});
export const eventsSchema = z.object({
  robot_id: z.string(),
  from_ms: time,
  to_ms: time,
  events: z.array(eventSchema),
});
const tracking = z.object({ rmse: n, mae: n, max_abs: n });
export const metricsSchema = z.object({
  robot_id: z.string(),
  from_ms: time,
  to_ms: time,
  samples: time,
  duration_s: n,
  status_counts: z.record(z.string(), n),
  tf_availability: n,
  distance_m: n,
  displacement_m: n,
  path_efficiency: n.nullable(),
  total_rotation_rad: n,
  avg_speed_mps: n,
  max_speed_mps: n,
  path_speed_mps: n,
  avg_angular_speed_rps: n,
  idle_ratio: n,
  moving_ratio: n,
  linear_tracking: tracking,
  angular_tracking: tracking,
  gaps: time,
  gap_time_s: n,
});
export const bucketSchema = z.object({
  t: time,
  samples: time,
  tf_availability: n,
  distance_m: n,
  avg_speed_mps: n,
  avg_cmd_speed_mps: n,
  avg_angular_speed_rps: n,
  linear_rmse: n,
  angular_rmse: n,
});
export const timeseriesSchema = z.object({
  robot_id: z.string(),
  from_ms: time,
  to_ms: time,
  bucket_s: n,
  buckets: z.array(bucketSchema),
});
