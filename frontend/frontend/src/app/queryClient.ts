import { QueryClient } from '@tanstack/react-query';
import { settings } from '../config/constants';
import { ApiError } from '../api/httpClient';
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: settings.pollMs,
      gcTime: settings.queryGcMs,
      retry: (count, error) =>
        count < 1 && !(error instanceof ApiError && error.status && error.status < 500),
      refetchOnWindowFocus: true,
    },
  },
});
