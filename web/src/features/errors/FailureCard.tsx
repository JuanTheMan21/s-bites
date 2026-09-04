import { useState } from 'react'
import { Card } from '@/components/Card'

export function FailureCard({ error }: { error: string | null }) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <Card className="border-signal-bad/25 bg-signal-bad/[.04] p-6">
      <p className="font-display text-xl text-ink-900">This video couldn't be finished.</p>
      <p className="mt-1.5 text-base text-ink-500">
        The pipeline hit an error it couldn't recover from on its own. You can retry from where
        it left off.
      </p>
      {error && (
        <div className="mt-3">
          <button
            onClick={() => setShowDetails((v) => !v)}
            className="font-mono text-xs text-ink-500 underline decoration-dotted transition-colors duration-(--duration-1) hover:text-signal-bad"
          >
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
          {showDetails && (
            <pre className="mt-2 overflow-x-auto rounded-md bg-paper-0 p-3 font-mono text-xs text-signal-bad">
              {error}
            </pre>
          )}
        </div>
      )}
    </Card>
  )
}
