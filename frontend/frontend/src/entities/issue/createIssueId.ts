import type { RobotEvent } from './model';
// Canonical, reversible tuple encoding has no hash collisions and distinguishes null from "".
export function createIssueId(robotId: string, event: RobotEvent): string {
  return JSON.stringify([robotId, event.type, event.start_ms, event.end_ms, event.message]);
}
