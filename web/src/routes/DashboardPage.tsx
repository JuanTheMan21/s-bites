import { JobList } from '@/features/dashboard/JobList'

export function DashboardPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-16">
      <h1 className="font-display text-3xl text-ink-900">Your videos</h1>
      <JobList />
    </div>
  )
}
