import { settings } from '../../config/constants';
export function retryDelay(attempt: number, random: () => number = Math.random): number {
  const base =
    settings.retryStepsMs[Math.min(Math.max(0, attempt), settings.retryStepsMs.length - 1)];
  return Math.min(30000, Math.round(base * (1 + settings.jitter * (random() * 2 - 1))));
}
