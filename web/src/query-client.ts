import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export const jobKeys = {
  list: () => ['jobs'] as const,
  detail: (jobId: string) => ['job', jobId] as const,
  stages: (jobId: string) => ['job', jobId, 'stages'] as const,
}
