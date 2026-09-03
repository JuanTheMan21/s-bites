import { useQuery } from '@tanstack/react-query'
import { fetchJob } from '@/adapters/job-adapter'
import { jobKeys } from '@/query-client'

const POLL_MS = 15000

export function useJobQuery(jobId: string) {
  return useQuery({
    queryKey: jobKeys.detail(jobId),
    queryFn: () => fetchJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      const terminal = status === 'succeeded' || status === 'failed'
      return terminal ? false : POLL_MS
    },
  })
}
