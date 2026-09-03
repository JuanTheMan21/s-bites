import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, createJob, fetchJobList, resumeJobRequest } from '@/adapters/job-adapter'
import type { JobView } from '@/domain/job'
import { jobKeys } from '@/query-client'

const POLL_MS = 5000

export function useJobsQuery() {
  return useQuery({
    queryKey: jobKeys.list(),
    queryFn: fetchJobList,
    refetchInterval: (query) => {
      const jobs = query.state.data as JobView[] | undefined
      const anyActive = jobs?.some((j) => j.status === 'queued' || j.status === 'running')
      return anyActive ?? true ? POLL_MS : false
    },
  })
}

export function useSubmitJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createJob,
    onSuccess: (job) => {
      queryClient.setQueryData(jobKeys.detail(job.jobId), job)
      queryClient.setQueryData<JobView[]>(jobKeys.list(), (existing) => [
        job,
        ...(existing ?? []),
      ])
    },
  })
}

export function useResumeJob(onConflict: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: resumeJobRequest,
    onSuccess: (job) => {
      queryClient.setQueryData(jobKeys.detail(job.jobId), job)
      queryClient.invalidateQueries({ queryKey: jobKeys.list() })
    },
    onError: (error: unknown) => {
      // 409: someone else already resumed this job between the button rendering and the click
      // landing -- a real, expected race, not a bug, so it gets a toast instead of an error
      // boundary.
      if (error instanceof ApiError && error.status === 409) {
        onConflict()
        return
      }
      throw error
    },
  })
}
