import { ru } from '../../shared/lib/ru';
import { createIssueId } from './createIssueId';
import type { Issue, RobotEvent, StoredIssueStatus } from './model';
export function mapEventToIssue(
  robotId: string,
  event: RobotEvent,
  status?: StoredIssueStatus,
): Issue {
  const id = createIssueId(robotId, event);
  return {
    id,
    robotId,
    type: event.type,
    title: ru.types[event.type],
    description: ru.descriptions[event.type],
    startMs: event.start_ms,
    endMs: event.end_ms,
    durationS: event.duration_s,
    samples: event.samples,
    sourceMessage: event.message,
    resolved: status?.id === id ? status.resolved : false,
    resolvedAt: status?.id === id ? status.resolvedAt : null,
  };
}
