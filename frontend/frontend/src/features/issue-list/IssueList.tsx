import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Search } from 'lucide-react';
import type { Issue } from '../../entities/issue/model';
import { issueStatusRepository, type IssueStatusRepository } from '../../db/issueStatusRepository';
import { ru } from '../../shared/lib/ru';
import { dateTime } from '../../shared/lib/date';
import { number } from '../../shared/lib/number';
import { settings } from '../../config/constants';
import { ResourceState, type ResourceStatus } from '../../shared/ui/ResourceState';
interface Filters {
  state: string;
  type: string;
  search: string;
  sort: string;
}
export function IssueList({
  issues,
  repository = issueStatusRepository,
  ...status
}: ResourceStatus & { issues: Issue[]; repository?: IssueStatusRepository }) {
  const { register, watch } = useForm<Filters>({
    defaultValues: { state: 'all', type: 'all', search: '', sort: 'newest' },
  });
  const filters = watch();
  const [overrides, setOverrides] = useState<
    Record<string, { resolved: boolean; resolvedAt: number | null }>
  >({});
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(settings.issuesPageSize);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const rows = useMemo(
    () => issues.map((i) => ({ ...i, ...overrides[i.id] })),
    [issues, overrides],
  );
  const open = rows.filter((i) => !i.resolved).length;
  const visible = rows
    .filter(
      (i) =>
        (filters.state === 'all' || i.resolved === (filters.state === 'closed')) &&
        (filters.type === 'all' || i.type === filters.type) &&
        [i.description, i.title, i.sourceMessage ?? '']
          .join(' ')
          .toLocaleLowerCase()
          .includes(filters.search.toLocaleLowerCase()),
    )
    .sort(
      (a, b) =>
        Number(a.resolved) - Number(b.resolved) ||
        (filters.sort === 'newest' ? b.startMs - a.startMs : a.startMs - b.startMs) ||
        a.id.localeCompare(b.id),
    );
  async function toggle(issue: Issue) {
    if (pending.has(issue.id)) return;
    const old = overrides[issue.id];
    const next = { resolved: !issue.resolved, resolvedAt: !issue.resolved ? Date.now() : null };
    setOverrides((values) => ({ ...values, [issue.id]: next }));
    setPending((values) => new Set(values).add(issue.id));
    setError(null);
    try {
      await repository.setResolved(issue.id, next.resolved);
    } catch {
      if (mounted.current) {
        setOverrides((values) => {
          const copy = { ...values };
          if (old) copy[issue.id] = old;
          else delete copy[issue.id];
          return copy;
        });
        setError(ru.saveError);
      }
    } finally {
      if (mounted.current)
        setPending((values) => {
          const copy = new Set(values);
          copy.delete(issue.id);
          return copy;
        });
    }
  }
  return (
    <>
      <div className="issue-summary">
        <span className="pill warn">
          {open} {ru.open.toLocaleLowerCase()}
        </span>
        <span className="pill muted">
          {rows.length - open} {ru.closed.toLocaleLowerCase()}
        </span>
      </div>
      <form
        className="issue-filters"
        onSubmit={(e) => e.preventDefault()}
        onChange={() => setLimit(settings.issuesPageSize)}
      >
        <label className="search-box">
          <Search size={16} />
          <input {...register('search')} aria-label={ru.search} placeholder={ru.search} />
        </label>
        <select {...register('state')} aria-label={ru.status}>
          <option value="all">{ru.all}</option>
          <option value="open">{ru.open}</option>
          <option value="closed">{ru.closed}</option>
        </select>
        <select {...register('type')} aria-label={ru.type}>
          <option value="all">
            {ru.type}: {ru.all}
          </option>
          {Object.entries(ru.types).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <select {...register('sort')} aria-label={ru.sort}>
          <option value="newest">{ru.newest}</option>
          <option value="oldest">{ru.oldest}</option>
        </select>
      </form>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      <ResourceState {...status}>
        {!visible.length ? (
          <div className="empty-state">{ru.noIssues}</div>
        ) : (
          <ul className="issue-list">
            {visible.slice(0, limit).map((issue) => (
              <li key={issue.id} className={'issue ' + (issue.resolved ? 'resolved' : '')}>
                <input
                  type="checkbox"
                  checked={issue.resolved}
                  disabled={pending.has(issue.id)}
                  aria-label={ru.resolve + ': ' + issue.title + ' · ' + dateTime(issue.startMs)}
                  onChange={() => void toggle(issue)}
                />
                <div className="issue-body">
                  <div className="issue-title">
                    <h3>{issue.title}</h3>
                    <span className={'event-tag ' + issue.type.toLowerCase()}>{issue.type}</span>
                    <span className="issue-status">
                      {pending.has(issue.id)
                        ? ru.storagePending
                        : issue.resolved
                          ? ru.closedSingle
                          : ru.openSingle}
                    </span>
                  </div>
                  <p>{issue.description}</p>
                  <dl className="issue-details">
                    <div>
                      <dt>{ru.robot}</dt>
                      <dd>{issue.robotId}</dd>
                    </div>
                    <div>
                      <dt>{ru.from}</dt>
                      <dd>{dateTime(issue.startMs)}</dd>
                    </div>
                    <div>
                      <dt>{ru.to}</dt>
                      <dd>{dateTime(issue.endMs)}</dd>
                    </div>
                    <div>
                      <dt>{ru.duration}</dt>
                      <dd>
                        {number(issue.durationS)} {ru.second}
                      </dd>
                    </div>
                    <div>
                      <dt>{ru.samples}</dt>
                      <dd>{number(issue.samples, 0)}</dd>
                    </div>
                  </dl>
                  {issue.sourceMessage && (
                    <p className="source-message">
                      {ru.source}: {issue.sourceMessage}
                    </p>
                  )}
                  {issue.resolvedAt && (
                    <small>
                      {ru.resolvedAt}: {dateTime(issue.resolvedAt)}
                    </small>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </ResourceState>
      {visible.length > limit && (
        <button
          className="text-button load-more"
          onClick={() => setLimit((v) => v + settings.issuesPageSize)}
        >
          {ru.more}
        </button>
      )}
    </>
  );
}
