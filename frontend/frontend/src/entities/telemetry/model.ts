import type { z } from 'zod';
import type {
  pointSchema,
  poseSchema,
  twistSchema,
  pageSchema,
  trajectorySchema,
  trajectoryPointSchema,
  metricsSchema,
  timeseriesSchema,
  bucketSchema,
} from './schemas';
export type TelemetryPoint = z.infer<typeof pointSchema>;
export type TelemetryStatus = TelemetryPoint['status'];
export type Pose = z.infer<typeof poseSchema>;
export type Twist = z.infer<typeof twistSchema>;
export type TelemetryPage = z.infer<typeof pageSchema>;
export type Trajectory = z.infer<typeof trajectorySchema>;
export type TrajectoryPoint = z.infer<typeof trajectoryPointSchema>;
export type Metrics = z.infer<typeof metricsSchema>;
export type MetricsBucket = z.infer<typeof bucketSchema>;
export type MetricsTimeseries = z.infer<typeof timeseriesSchema>;
