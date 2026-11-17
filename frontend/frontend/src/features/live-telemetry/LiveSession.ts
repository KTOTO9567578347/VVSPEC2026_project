import { env } from '../../config/env';
import { settings } from '../../config/constants';
import { telemetryApi } from '../../api/telemetryApi';
import { telemetryRepository, type TelemetryRepository } from '../../db/telemetryRepository';
import { liveSchema } from '../../entities/telemetry/schemas';
import type { TelemetryPoint } from '../../entities/telemetry/model';
import { mergeTelemetryPoints } from '../../entities/telemetry/mergeTelemetryPoints';
import { retryDelay } from '../../shared/lib/retry';
import { ru } from '../../shared/lib/ru';
export type ConnectionState =
  'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';
export interface LiveState {
  points: TelemetryPoint[];
  connection: ConnectionState;
  loading: boolean;
  syncing: boolean;
  sampled: boolean;
  error: string | null;
  storageError: string | null;
  updatedAt: number | null;
}
export const emptyLiveState = (): LiveState => ({
  points: [],
  connection: 'connecting',
  loading: true,
  syncing: false,
  sampled: false,
  error: null,
  storageError: null,
  updatedAt: null,
});
interface Options {
  robotId: string;
  windowS: number;
  onChange: (state: LiveState) => void;
  initialResources?: () => Promise<unknown>;
  repository?: TelemetryRepository;
  socketFactory?: (url: string) => WebSocket;
}
export class LiveSession {
  private state = emptyLiveState();
  private disposed = false;
  private abort = new AbortController();
  private socket?: WebSocket;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private openTimer?: ReturnType<typeof setTimeout>;
  private pollTimer?: ReturnType<typeof setInterval>;
  private emitTimer?: ReturnType<typeof setTimeout>;
  private attempt = 0;
  private syncedThrough = 0;
  private syncPromise?: Promise<void>;
  private writes = Promise.resolve();
  private pendingWrites: TelemetryPoint[] = [];
  private writing = false;
  private persistenceFailed = false;
  private repository: TelemetryRepository;
  private socketFactory: (url: string) => WebSocket;
  constructor(private options: Options) {
    this.repository = options.repository ?? telemetryRepository;
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url));
  }
  private publish(immediate = true) {
    if (this.disposed) return;
    if (immediate) {
      if (this.emitTimer) clearTimeout(this.emitTimer);
      this.emitTimer = undefined;
      this.options.onChange({ ...this.state });
    } else if (!this.emitTimer)
      this.emitTimer = setTimeout(() => {
        this.emitTimer = undefined;
        this.publish();
      }, settings.uiBatchMs);
  }
  private persist(points: TelemetryPoint[]) {
    this.pendingWrites = mergeTelemetryPoints(this.pendingWrites, points);
    if (this.writing) return this.writes;
    this.writing = true;
    this.writes = (async () => {
      // Coalesce arrivals while IndexedDB is busy; the pending queue is bounded too.
      do {
        const batch = this.persistenceFailed ? this.state.points : this.pendingWrites;
        this.pendingWrites = [];
        try {
          await this.repository.save(this.options.robotId, batch, this.state.sampled);
          if (this.persistenceFailed) {
            this.state.storageError = null;
            this.publish();
          }
          this.persistenceFailed = false;
        } catch {
          this.persistenceFailed = true;
          this.state.storageError = ru.storageError;
          this.publish();
        }
      } while (this.pendingWrites.length);
    })().finally(() => {
      this.writing = false;
    });
    return this.writes;
  }
  private merge(points: TelemetryPoint[]) {
    if (this.disposed) return;
    this.state.points = mergeTelemetryPoints(this.state.points, points);
    this.state.updatedAt = Date.now();
    void this.persist(points);
    this.publish(false);
  }
  async start() {
    const startedAt = Date.now();
    this.syncedThrough = Math.max(0, startedAt - this.options.windowS * 1000);
    try {
      const [points, cursor] = await Promise.all([
        this.repository.load(this.options.robotId),
        this.repository.cursor(this.options.robotId),
      ]);
      if (this.disposed) return;
      this.state.points = mergeTelemetryPoints([], points);
      this.state.sampled = cursor?.sampled ?? false;
      this.syncedThrough = cursor?.syncedThrough ?? cursor?.lastTimestamp ?? this.syncedThrough;
      this.publish();
    } catch {
      this.state.storageError = ru.storageError;
      this.publish();
    }
    if (this.disposed) return;
    await Promise.allSettled([
      this.synchronize(
        Math.min(this.syncedThrough, Math.max(0, startedAt - this.options.windowS * 1000)),
      ),
      this.options.initialResources?.(),
    ]);
    if (this.disposed) return;
    this.state.loading = false;
    this.open();
    // Also repairs a failed catch-up while the socket remains open, and silent stream losses.
    this.pollTimer = setInterval(() => {
      void this.synchronize();
    }, settings.pollMs);
  }
  synchronize(from = this.syncedThrough): Promise<void> {
    if (this.disposed) return Promise.resolve();
    if (this.syncPromise) return this.syncPromise;
    const to = Date.now();
    this.state.syncing = true;
    this.publish();
    this.syncPromise = (async () => {
      try {
        const page = await telemetryApi.history(
          this.options.robotId,
          { from_ms: Math.min(from, to), to_ms: to },
          this.abort.signal,
        );
        if (this.disposed) return;
        this.state.sampled ||= page.stride > 1;
        this.merge(page.points);
        await this.writes;
        // Server time is not a delivery watermark: a batch can be committed after the
        // snapshot with an older timestamp. Overlap from the last REST-confirmed point.
        const confirmedTimestamp = page.points.reduce(
          (latest, point) => Math.max(latest, Math.min(point.timestamp_ms, to)),
          Math.min(this.syncedThrough, to),
        );
        try {
          if (!this.persistenceFailed)
            await this.repository.markSynced(this.options.robotId, confirmedTimestamp);
        } catch {
          this.state.storageError = ru.storageError;
        }
        this.syncedThrough = confirmedTimestamp;
        this.state.error = null;
      } catch (error) {
        if (!this.disposed) this.state.error = error instanceof Error ? error.message : ru.error;
      } finally {
        this.syncPromise = undefined;
        this.state.syncing = false;
        this.publish();
      }
    })();
    return this.syncPromise;
  }
  private open() {
    if (this.disposed) return;
    this.state.connection = this.attempt ? 'reconnecting' : 'connecting';
    this.publish();
    const url = new URL(env.VITE_WS_BASE_URL.replace(/\/$/, '') + '/ws/live');
    url.searchParams.set('robot_id', this.options.robotId);
    let socket: WebSocket;
    try {
      socket = this.socketFactory(url.toString());
      this.socket = socket;
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.openTimer = setTimeout(() => {
      socket.close();
      this.scheduleReconnect();
    }, settings.socketOpenTimeoutMs);
    socket.onopen = () => {
      if (this.disposed) return;
      clearTimeout(this.openTimer);
      this.attempt = 0;
      this.state.connection = 'connected';
      this.publish();
      // Live batches can arrive during REST. Merge them immediately; REST deduplicates the overlap.
      void this.synchronize();
    };
    socket.onmessage = (message) => {
      if (this.disposed) return;
      try {
        if (typeof message.data !== 'string') throw new Error('Invalid frame');
        const parsed = liveSchema.safeParse(JSON.parse(message.data));
        if (!parsed.success) throw new Error('Invalid payload');
        if (parsed.data.robot_id !== this.options.robotId) return;
        this.merge(parsed.data.points);
      } catch {
        this.state.error = ru.socketInvalid;
        this.publish();
        void this.synchronize();
      }
    };
    socket.onerror = () => {
      if (!this.disposed) {
        this.state.connection = 'error';
        this.state.error = ru.socketError;
        this.publish();
        socket.close();
        this.scheduleReconnect();
      }
    };
    socket.onclose = () => {
      clearTimeout(this.openTimer);
      this.scheduleReconnect();
    };
  }
  private scheduleReconnect() {
    if (this.disposed || this.reconnectTimer) return;
    this.state.connection = 'reconnecting';
    this.publish();
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.open();
    }, retryDelay(this.attempt++));
  }
  refresh() {
    return this.synchronize(
      Math.min(this.syncedThrough, Math.max(0, Date.now() - this.options.windowS * 1000)),
    );
  }
  stop() {
    this.disposed = true;
    this.abort.abort();
    clearTimeout(this.reconnectTimer);
    clearTimeout(this.openTimer);
    clearTimeout(this.emitTimer);
    clearInterval(this.pollTimer);
    if (this.socket) {
      this.socket.onopen = null;
      this.socket.onmessage = null;
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.close();
    }
  }
}
