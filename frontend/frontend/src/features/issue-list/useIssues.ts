import { useEffect, useState } from 'react';
import { issueStatusRepository } from '../../db/issueStatusRepository';
import { mapEventToIssue } from '../../entities/issue/mapEventToIssue';
import type { Issue, RobotEvent } from '../../entities/issue/model';
import { ru } from '../../shared/lib/ru';
export function useIssues(robotId: string, events: RobotEvent[] | undefined) {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const task = events
      ? issueStatusRepository.sync(robotId, events)
      : issueStatusRepository.getAll(robotId);
    void task
      .then((rows) => {
        if (active) setIssues(rows);
      })
      .catch(() => {
        if (active) {
          setError(ru.storageError);
          if (events)
            setIssues((old) => {
              const rows = new Map(old.map((i) => [i.id, i]));
              for (const event of events) {
                const i = mapEventToIssue(robotId, event);
                if (!rows.has(i.id)) rows.set(i.id, i);
              }
              return [...rows.values()];
            });
        }
      });
    return () => {
      active = false;
    };
  }, [robotId, events]);
  return { issues, error };
}
