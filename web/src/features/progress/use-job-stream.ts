import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { STAGE_EVENT_NAME, openJobEventStream, toStageEvent } from '@/adapters/stage-adapter'
import type { JobView } from '@/domain/job'
import type { StageEvent } from '@/domain/stage'
import { jobKeys } from '@/query-client'

const ERROR_BURST_WINDOW_MS = 30000
const ERROR_BURST_THRESHOLD = 3

function isAlreadyTerminal(job: JobView | undefined): boolean {
  return job?.status === 'succeeded' || job?.status === 'failed'
}

/**
 * Subscribes to a job's SSE stream and returns the accumulated transition log plus a connection
 * state a progress view can render. Four cases the backend actually produces, all handled here
 * (see api/jobs.py and api/runner.py):
 *
 * 1. The server names every message `stage`, never the default `message` event -- `onmessage`
 *    would silently never fire, so this always binds `addEventListener(STAGE_EVENT_NAME, ...)`.
 * 2. A terminal `status` event (`terminal: true`) closes the EventSource itself. Native
 *    `EventSource` auto-reconnects when a server closes a stream normally, so *not* closing here
 *    would reconnect forever into the already-terminal branch's single report-and-close.
 * 3. A retryable failure (`terminal: false`) is left alone -- the stream stays open across the
 *    runner's automatic retry, exactly as the backend intends.
 * 4. If the cached job is already terminal, no stream opens at all -- reflected in the initial
 *    state itself (a lazy useState initializer), not a setState call inside the effect body.
 */
export function useJobStream(jobId: string, job: JobView | undefined) {
  const queryClient = useQueryClient()
  const [events, setEvents] = useState<StageEvent[]>([])
  const [connection, setConnection] = useState<'connecting' | 'open' | 'reconnecting' | 'closed'>(
    () => (isAlreadyTerminal(job) ? 'closed' : 'connecting'),
  )
  const errorTimestamps = useRef<number[]>([])

  useEffect(() => {
    if (isAlreadyTerminal(job)) return

    const source = openJobEventStream(jobId)

    source.addEventListener('open', () => {
      setConnection('open')
      errorTimestamps.current = []
      // A reconnect can miss whatever happened while disconnected -- refetch ground truth rather
      // than trust the (possibly stale) transition log alone.
      queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) })
    })

    source.addEventListener(STAGE_EVENT_NAME, (raw: MessageEvent<string>) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(raw.data)
      } catch {
        parsed = null
      }
      const event = toStageEvent(parsed)
      setEvents((prev) => [...prev, event])

      if (event.kind === 'transition' && event.edge === 'end') {
        // A stage just finished -- the job's real tiers/durations/clip_key may have changed.
        queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) })
      }
      if (event.kind === 'status' && event.terminal) {
        queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) })
        queryClient.invalidateQueries({ queryKey: jobKeys.list() })
        source.close()
        setConnection('closed')
      }
    })

    source.addEventListener('error', () => {
      const now = Date.now()
      errorTimestamps.current = [...errorTimestamps.current, now].filter(
        (t) => now - t < ERROR_BURST_WINDOW_MS,
      )
      setConnection(
        errorTimestamps.current.length >= ERROR_BURST_THRESHOLD ? 'reconnecting' : 'connecting',
      )
    })

    return () => source.close()
    // job is intentionally excluded: a job becoming terminal mid-subscription is handled by the
    // status-event listener above (which closes the source itself), not by re-running this
    // effect -- only the job_id identifies which stream to open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, queryClient])

  return { events, connection }
}
