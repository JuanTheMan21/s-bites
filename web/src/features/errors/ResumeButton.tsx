import { Button } from '@/components/Button'
import { useToastStore } from '@/components/toast-store'
import { useResumeJob } from '@/features/jobs/use-jobs'

export function ResumeButton({ jobId }: { jobId: string }) {
  const push = useToastStore((s) => s.push)
  const resume = useResumeJob(() =>
    push('This job was already resumed elsewhere -- refresh to see its current status.', 'bad'),
  )

  return (
    <Button onClick={() => resume.mutate(jobId)} disabled={resume.isPending}>
      {resume.isPending ? 'Resuming…' : 'Resume'}
    </Button>
  )
}
