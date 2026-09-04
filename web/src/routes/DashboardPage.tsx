import { JobList } from '@/features/dashboard/JobList'

export function DashboardPage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-8 py-16">
      <h1 className="font-display text-4xl text-ink-900">Your videos</h1>
      <JobList />
    </div>
  )
}
