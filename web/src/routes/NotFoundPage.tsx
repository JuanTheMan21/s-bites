import { Link } from 'react-router-dom'
import { Button } from '@/components/Button'
import { EmptyState } from '@/components/EmptyState'

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-24">
      <EmptyState
        title="Page not found"
        description="That page doesn't exist."
        action={
          <Link to="/">
            <Button>Back to studio</Button>
          </Link>
        }
      />
    </div>
  )
}
