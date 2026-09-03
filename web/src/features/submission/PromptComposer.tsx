import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/Button'
import { classNames } from '@/components/class-names'
import { useToastStore } from '@/components/toast-store'
import { useSubmitJob } from '@/features/jobs/use-jobs'
import { describeSubmitError } from '@/features/jobs/submit-error'

const DURATION_OPTIONS = [
  { label: '3 min', ms: 180_000 },
  { label: '7 min', ms: 420_000 },
  { label: '10 min', ms: 600_000 },
]

export function PromptComposer() {
  const [topic, setTopic] = useState('')
  const [durationMs, setDurationMs] = useState(DURATION_OPTIONS[1]!.ms)
  const navigate = useNavigate()
  const push = useToastStore((s) => s.push)
  const submit = useSubmitJob((error) => push(describeSubmitError(error), 'bad'))

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim() || submit.isPending) return
    submit.mutate(
      { topic: topic.trim(), targetDurationMs: durationMs },
      { onSuccess: (job) => navigate(`/jobs/${job.jobId}`, { replace: true }) },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-2">
        <span className="font-mono text-xs tracking-wide text-ink-500 uppercase">Topic</span>
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Teach me about SQL injection"
          rows={3}
          className="resize-none rounded-md border border-ink-300/30 bg-paper-0 px-4 py-3 font-display text-2xl text-ink-900 placeholder:text-ink-300 focus:border-accent focus:outline-none"
        />
      </label>

      <div className="flex items-center gap-2">
        {DURATION_OPTIONS.map((option) => (
          <button
            key={option.ms}
            type="button"
            onClick={() => setDurationMs(option.ms)}
            className={classNames(
              'rounded-full border px-3 py-1.5 font-mono text-xs transition-colors duration-(--duration-1)',
              option.ms === durationMs
                ? 'border-accent bg-accent-tint text-accent'
                : 'border-ink-300/30 text-ink-500 hover:border-ink-300/60',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <Button type="submit" disabled={!topic.trim() || submit.isPending} className="self-start">
        {submit.isPending ? 'Starting…' : 'Make the video'}
      </Button>
    </form>
  )
}
