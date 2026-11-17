import { RefreshCw, Moon, Radio } from 'lucide-react';
import type { Robot } from '../../entities/robot/model';
import type { LiveState } from '../../features/live-telemetry/LiveSession';
import { settings } from '../../config/constants';
import { useClock } from '../../shared/hooks/useClock';
import { time } from '../../shared/lib/date';
import { ru } from '../../shared/lib/ru';
interface Props {
  robots: Robot[];
  robotId: string;
  onSelect: (id: string) => void;
  live?: LiveState;
  onRefresh: () => void;
  onTheme: () => void;
  robotsStale: boolean;
}
export function Header({
  robots,
  robotId,
  onSelect,
  live,
  onRefresh,
  onTheme,
  robotsStale,
}: Props) {
  const now = useClock();
  const robot = robots.find((r) => r.id === robotId);
  const latest = live?.points.at(-1) ?? robot?.last_point;
  const fresh = latest && now - latest.timestamp_ms <= settings.staleMs;
  return (
    <header className="topbar">
      <div className="brand-mobile">{ru.app}</div>
      <div className="robot-select">
        <span className="robot-icon">
          <Radio size={19} />
        </span>
        <label>
          <span>{ru.robot}</span>
          <select
            aria-label={ru.selectRobot}
            value={robotId}
            onChange={(e) => onSelect(e.target.value)}
          >
            {!robots.length && <option value="">{ru.noRobots}</option>}
            {robotId && !robot && <option value={robotId}>{robotId}</option>}
            {robots.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id}
              </option>
            ))}
          </select>
        </label>
        <span className={'pill ' + (robot?.online && !robotsStale ? 'good' : 'muted')}>
          <i />
          {robotsStale ? ru.unknown : robot?.online ? ru.online : ru.offline}
        </span>
      </div>
      <div className="header-status" aria-live="polite">
        <span className={'connection ' + (live?.connection === 'connected' ? 'good-text' : '')}>
          <i />
          {ru.connection[live?.connection ?? 'disconnected']}
        </span>
        <small>
          {ru.last} {time(latest?.timestamp_ms)} · {fresh ? ru.fresh : ru.stale}
        </small>
      </div>
      <button
        className="icon-button"
        onClick={onRefresh}
        aria-label={ru.refresh}
        title={ru.refresh}
      >
        <RefreshCw size={18} className={live?.syncing ? 'spin' : ''} />
      </button>
      <button className="icon-button" onClick={onTheme} aria-label={ru.theme} title={ru.theme}>
        <Moon size={18} />
      </button>
    </header>
  );
}
