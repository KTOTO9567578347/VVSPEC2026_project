import type { z } from 'zod';
import type { eventSchema } from '../telemetry/schemas';
export type RobotEvent = z.infer<typeof eventSchema>;
export type EventType = RobotEvent['type'];
export interface StoredIssueStatus {
  id: string;
  robotId: string;
  resolved: boolean;
  resolvedAt: number | null;
}
export interface Issue extends StoredIssueStatus {
  type: EventType;
  title: string;
  description: string;
  startMs: number;
  endMs: number;
  durationS: number;
  samples: number;
  sourceMessage: string | null;
}
