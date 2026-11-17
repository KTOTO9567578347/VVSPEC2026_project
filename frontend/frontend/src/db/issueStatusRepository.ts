import { db, type ObservatoryDatabase } from './database';
import type { Issue, RobotEvent, StoredIssueStatus } from '../entities/issue/model';
import { mapEventToIssue } from '../entities/issue/mapEventToIssue';
export interface IssueStatusRepository {
  getAll(robotId: string): Promise<StoredIssueStatus[]>;
  setResolved(issueId: string, resolved: boolean): Promise<void>;
}
export class DexieIssueStatusRepository implements IssueStatusRepository {
  constructor(private database: ObservatoryDatabase = db) {}
  getAll(robotId: string): Promise<Issue[]> {
    return this.database.issues.where('robotId').equals(robotId).toArray();
  }
  async setResolved(id: string, resolved: boolean) {
    const count = await this.database.issues.update(id, {
      resolved,
      resolvedAt: resolved ? Date.now() : null,
    });
    if (!count) throw new Error('Issue not found');
  }
  async sync(robotId: string, events: RobotEvent[]): Promise<Issue[]> {
    return this.database.transaction('rw', this.database.issues, async () => {
      for (const event of events) {
        const issue = mapEventToIssue(robotId, event);
        const stored = await this.database.issues.get(issue.id);
        await this.database.issues.put(mapEventToIssue(robotId, event, stored));
      }
      return this.getAll(robotId);
    });
  }
}
export const issueStatusRepository = new DexieIssueStatusRepository();
