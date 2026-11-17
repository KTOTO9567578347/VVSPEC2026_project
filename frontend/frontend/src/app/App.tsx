import { useEffect } from 'react';
import { Activity, LayoutDashboard, ShieldCheck, Route } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useRobots } from '../features/robot-selector/useRobots';
import { usePreference } from '../shared/hooks/usePreferences';
import { Dashboard } from '../pages/dashboard/Dashboard';
import { Header } from '../widgets/header/Header';
import { ResourceState } from '../shared/ui/ResourceState';
import { settings } from '../config/constants';
import { ru } from '../shared/lib/ru';
export function App() {
  const robots = useRobots();
  const client = useQueryClient();
  const selected = usePreference('robot', '');
  const windowPreference = usePreference('window', String(settings.defaultWindow));
  const theme = usePreference('theme', 'light');
  const robotId = selected.value || robots.data?.[0]?.id || '';
  const rawWindow = Number(windowPreference.value);
  const windowS =
    Number.isInteger(rawWindow) && rawWindow >= 10 && rawWindow <= 86400
      ? rawWindow
      : settings.defaultWindow;
  useEffect(() => {
    document.documentElement.dataset.theme = theme.value === 'dark' ? 'dark' : 'light';
  }, [theme.value]);
  const toggleTheme = () => theme.setValue(theme.value === 'dark' ? 'light' : 'dark');
  const list = robots.data ?? [];
  const listStale = !!robots.error || Date.now() - robots.dataUpdatedAt > settings.pollMs * 2;
  const error =
    robots.error?.message ??
    robots.storageError ??
    selected.error ??
    theme.error ??
    windowPreference.error;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#main">
          <span className="brand-mark">
            <Route size={24} />
          </span>
          <div>
            <strong>{ru.app}</strong>
            <small>{ru.product}</small>
          </div>
        </a>
        <div className="sidebar-section">{ru.workspace}</div>
        <nav aria-label={ru.monitoring}>
          <a className="nav-item active" href="#main">
            <LayoutDashboard size={18} />
            {ru.monitoring}
          </a>
          <a className="nav-item" href="#issues">
            <Activity size={18} />
            {ru.issues}
          </a>
        </nav>
        <div className="sidebar-foot">
          <ShieldCheck size={22} />
          <strong>{ru.local}</strong>
          <p>{ru.reconnectHint}</p>
          <span className="sidebar-version">VVSPEC / 2026</span>
        </div>
      </aside>
      <div className="main-shell" id="main">
        {error && (
          <div className="global-notice notice error" role="alert">
            {error}
          </div>
        )}
        {robotId && selected.ready && windowPreference.ready ? (
          <Dashboard
            key={robotId + ':' + windowS}
            robotId={robotId}
            robots={list}
            onSelect={selected.setValue}
            onTheme={toggleTheme}
            windowS={windowS}
            onWindow={windowPreference.setValue}
            robotsStale={listStale}
          />
        ) : (
          <>
            <Header
              robots={list}
              robotId={robotId}
              onSelect={selected.setValue}
              onTheme={toggleTheme}
              robotsStale={listStale}
              onRefresh={() => void client.invalidateQueries({ queryKey: ['robots'] })}
            />
            <main className="dashboard">
              <h1>{ru.overview}</h1>
              <ResourceState loading={robots.isPending || !selected.ready}>
                <div className="empty-state">
                  <Activity size={36} />
                  <h2>{ru.noRobots}</h2>
                  <p>{robots.error ? ru.network : ru.noRobotsHint}</p>
                </div>
              </ResourceState>
            </main>
          </>
        )}
      </div>
    </div>
  );
}
