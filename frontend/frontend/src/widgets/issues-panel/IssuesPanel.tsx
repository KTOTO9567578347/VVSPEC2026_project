import { CircleAlert } from 'lucide-react';
import { useIssues } from '../../features/issue-list/useIssues';
import { IssueList } from '../../features/issue-list/IssueList';
import type { RobotEvent } from '../../entities/issue/model';
import type { ResourceStatus } from '../../shared/ui/ResourceState';
import { ru } from '../../shared/lib/ru';
export function IssuesPanel({
  robotId,
  events,
  ...status
}: ResourceStatus & { robotId: string; events: RobotEvent[] | undefined }) {
  const { issues, error } = useIssues(robotId, events);
  return (
    <section className="panel issues-panel" id="issues">
      <div className="panel-heading">
        <div>
          <h2>
            <CircleAlert size={19} />
            {ru.issues}
          </h2>
          <p>{ru.issueNote}</p>
        </div>
      </div>
      <IssueList
        key={robotId}
        issues={issues}
        {...status}
        loading={status.loading && !issues.length}
        error={error ?? status.error}
      />
    </section>
  );
}
