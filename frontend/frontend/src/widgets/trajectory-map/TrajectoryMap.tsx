import { memo, useMemo, useState } from 'react';
import { Crosshair, Expand, Minus, Plus } from 'lucide-react';
import type { Pose, TrajectoryPoint } from '../../entities/telemetry/model';
import { sampleForDisplay } from '../../entities/telemetry/mergeTelemetryPoints';
import { settings } from '../../config/constants';
import { number } from '../../shared/lib/number';
import { ru } from '../../shared/lib/ru';
import { ResourceState, type ResourceStatus } from '../../shared/ui/ResourceState';
interface Props extends ResourceStatus {
  points: TrajectoryPoint[];
  pose: Pose | null;
  lostPose: boolean;
}
export const TrajectoryMap = memo(function TrajectoryMap({
  points,
  pose,
  lostPose,
  ...status
}: Props) {
  const [follow, setFollow] = useState(false);
  const [zoom, setZoom] = useState(1);
  const geometry = useMemo(() => {
    const path = sampleForDisplay(points, settings.mapPoints);
    const all = pose ? [...path, { ...pose, t: 0 }] : path;
    let minX = 0,
      maxX = 8,
      minY = 0,
      maxY = 4;
    if (all.length) {
      minX = Infinity;
      maxX = -Infinity;
      minY = Infinity;
      maxY = -Infinity;
      for (const p of all) {
        minX = Math.min(minX, p.x);
        maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y);
        maxY = Math.max(maxY, p.y);
      }
    }
    const cx = follow && pose ? pose.x : (minX + maxX) / 2,
      cy = follow && pose ? pose.y : (minY + maxY) / 2;
    const span = Math.max(8, (maxX - minX) * 1.3, (maxY - minY) * 2.1) / zoom;
    const scale = 720 / span;
    const x = (n: number) => 400 + (n - cx) * scale;
    const y = (n: number) => 220 - (n - cy) * scale;
    const rough = span / 8;
    const base = 10 ** Math.floor(Math.log10(rough));
    const step = base * (rough / base > 5 ? 10 : rough / base > 2 ? 5 : 2);
    const xs = Array.from(
      { length: Math.ceil(span / step) + 2 },
      (_, i) => Math.floor((cx - span / 2) / step) * step + i * step,
    );
    const ys = Array.from(
      { length: Math.ceil((span * 0.5) / step) + 3 },
      (_, i) => Math.floor((cy - span * 0.25) / step) * step + i * step,
    );
    return { path, x, y, step, scale, xs, ys };
  }, [points, pose, follow, zoom]);
  return (
    <section className="panel map-panel">
      <div className="panel-heading">
        <div>
          <h2>{ru.trajectory}</h2>
          <p>{ru.localCoordinates}</p>
        </div>
        <span className="small-tag">XY</span>
      </div>
      <ResourceState {...status} empty={!points.length && !pose}>
        <div className="map-canvas">
          <svg viewBox="0 0 800 440" role="img" aria-label={ru.trajectory}>
            <defs>
              <pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="0.7" fill="currentColor" opacity=".16" />
              </pattern>
              <clipPath id="map-clip">
                <rect x="35" y="15" width="740" height="395" />
              </clipPath>
            </defs>
            <rect width="800" height="440" fill="url(#dots)" />
            <g clipPath="url(#map-clip)">
              {geometry.xs.map((v) => (
                <g key={'x' + v}>
                  <line
                    x1={geometry.x(v)}
                    x2={geometry.x(v)}
                    y1="15"
                    y2="410"
                    className="grid-line"
                  />
                  <text x={geometry.x(v) + 4} y="404" className="axis-label">
                    {number(v, 1)}
                  </text>
                </g>
              ))}
              {geometry.ys.map((v) => (
                <g key={'y' + v}>
                  <line
                    y1={geometry.y(v)}
                    y2={geometry.y(v)}
                    x1="35"
                    x2="775"
                    className="grid-line"
                  />
                  <text x="40" y={geometry.y(v) - 5} className="axis-label">
                    {number(v, 1)}
                  </text>
                </g>
              ))}
              <polyline
                points={geometry.path.map((p) => geometry.x(p.x) + ',' + geometry.y(p.y)).join(' ')}
                fill="none"
                stroke="var(--accent)"
                strokeWidth="3"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {geometry.path[0] && (
                <circle
                  cx={geometry.x(geometry.path[0].x)}
                  cy={geometry.y(geometry.path[0].y)}
                  r="6"
                  fill="var(--panel)"
                  stroke="var(--accent)"
                  strokeWidth="3"
                />
              )}
              {pose && (
                <g transform={'translate(' + geometry.x(pose.x) + ' ' + geometry.y(pose.y) + ')'}>
                  <circle r="22" fill="var(--accent)" opacity=".12" />
                  <circle r="12" fill="var(--panel)" stroke="var(--accent)" strokeWidth="2" />
                  <path
                    d="M 8 0 L -5 -5 L -3 0 L -5 5 Z"
                    fill="var(--accent)"
                    transform={'rotate(' + (-pose.yaw * 180) / Math.PI + ')'}
                  />
                </g>
              )}
            </g>
            <path
              d={'M 625 416 h ' + Math.min(geometry.step * geometry.scale, 130)}
              stroke="currentColor"
              strokeWidth="2"
            />
            <text x="625" y="402" className="axis-label">
              {number(Math.min(geometry.step * geometry.scale, 130) / geometry.scale)} {ru.meter}
            </text>
            <text x="760" y="430" className="axis-label">
              X
            </text>
            <text x="20" y="24" className="axis-label">
              Y
            </text>
          </svg>
          <div className="map-zoom">
            <button
              className="icon-button"
              aria-label={ru.zoomIn}
              onClick={() => setZoom((z) => Math.min(16, z * 1.5))}
            >
              <Plus size={17} />
            </button>
            <button
              className="icon-button"
              aria-label={ru.zoomOut}
              onClick={() => setZoom((z) => Math.max(0.25, z / 1.5))}
            >
              <Minus size={17} />
            </button>
          </div>
        </div>
      </ResourceState>
      {lostPose && <p className="notice warning">{ru.noPose}</p>}
      <footer className="map-footer">
        <div className="map-legend">
          <span>
            <i className="legend-line" />
            {ru.route}
          </span>
          <span>
            <i className="legend-ring" />
            {ru.start}
          </span>
        </div>
        <div className="map-actions">
          <button
            className="text-button"
            onClick={() => {
              setFollow(false);
              setZoom(1);
            }}
          >
            <Expand size={15} />
            {ru.fit}
          </button>
          <button
            className={'text-button ' + (follow ? 'selected' : '')}
            aria-pressed={follow}
            onClick={() => setFollow((v) => !v)}
          >
            <Crosshair size={15} />
            {ru.follow}
          </button>
        </div>
      </footer>
    </section>
  );
});
