import { z } from 'zod';
const schema = z.object({
  VITE_API_BASE_URL: z
    .url()
    .refine((v) => /^https?:\/\//.test(v), 'Нужен http:// или https://')
    .default('http://localhost:8000'),
  VITE_WS_BASE_URL: z
    .url()
    .refine((v) => /^wss?:\/\//.test(v), 'Нужен ws:// или wss://')
    .default('ws://localhost:8000'),
  VITE_TELEMETRY_HISTORY_LIMIT: z.coerce.number().int().min(100).max(50000).default(50000),
  VITE_DEFAULT_WINDOW_SECONDS: z.coerce.number().int().min(10).max(86400).default(600),
});
export const environment = schema.safeParse(import.meta.env);
export const configError = environment.success
  ? null
  : environment.error.issues.map((i) => i.path.join('.') + ': ' + i.message).join('; ');
export const env = environment.success ? environment.data : schema.parse({});
