import type { ReactNode } from 'react';
import { ru } from '../lib/ru';
export interface ResourceStatus {
  loading?: boolean;
  error?: Error | string | null;
  refreshing?: boolean;
  updatedAt?: number;
  stale?: boolean;
}
export function ResourceState({
  loading,
  error,
  refreshing,
  stale,
  children,
  empty = false,
}: ResourceStatus & { children?: ReactNode; empty?: boolean }) {
  return (
    <>
      {error && (
        <p className="notice error" role="alert">
          {typeof error === 'string' ? error : error.message}
        </p>
      )}
      {stale && (
        <p className="state-note">
          {ru.stale} · {ru.cached}
        </p>
      )}
      {loading ? (
        <div className="empty-state" role="status">
          <span className="loader" />
          {ru.loading}
        </div>
      ) : empty ? (
        <div className="empty-state">{ru.empty}</div>
      ) : (
        children
      )}
      {refreshing && !loading && (
        <span className="state-note" role="status">
          {ru.background}
        </span>
      )}
    </>
  );
}
