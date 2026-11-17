import type { z } from 'zod';
import type { robotSchema } from '../telemetry/schemas';
export type Robot = z.infer<typeof robotSchema>;
