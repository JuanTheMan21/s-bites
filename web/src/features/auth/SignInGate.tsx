import { useEffect, useState } from 'react'
import { authEnabled, currentUser, establishSession, signIn } from '@/adapters/auth-adapter'
import { Button } from '@/components/Button'
import type { SignedInUser } from '@/domain/user'

/** Nothing in the app renders until we know who is asking (T38A).
 *
 * A gate rather than per-route guards: every route here fetches job data on mount, so rendering
 * one before the session exists just produces a flash of 401s. The gate also establishes the API
 * session cookie, which the video, subtitles, SCORM and SSE URLs all depend on and which nothing
 * else would trigger.
 *
 * `authEnabled === false` (no `VITE_ENTRA_CLIENT_ID`) renders children immediately -- the local
 * `AUTH_ENV=none` path stays a first-class mode, not a broken one.
 */

type State = 'checking' | 'signed-out' | 'ready' | 'failed'

export function SignInGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>(authEnabled ? 'checking' : 'ready')
  const [user, setUser] = useState<SignedInUser | null>(null)

  useEffect(() => {
    if (!authEnabled) return
    let cancelled = false
    void (async () => {
      const account = currentUser()
      if (!account) {
        if (!cancelled) setState('signed-out')
        return
      }
      try {
        await establishSession()
        if (!cancelled) {
          setUser(account)
          setState('ready')
        }
      } catch {
        // A token that MSAL is happy with but the API rejects -- most often the tenant is not in
        // ENTRA_ALLOWED_TENANTS, or the required app role is missing. Both are "you are signed in
        // but not permitted here", which is a different message from "please sign in".
        if (!cancelled) setState('failed')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (state === 'ready') return <>{children}</>

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-6 px-8 text-center">
      {state === 'checking' && <p className="font-mono text-sm text-ink-500">Signing you in…</p>}

      {state === 'signed-out' && (
        <>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink-900">
            Sign in to skill-bites
          </h1>
          <p className="text-sm text-ink-500">
            Your videos are private to your account. Sign in with a Microsoft account to make one.
          </p>
          <Button onClick={() => void signIn()}>Sign in with Microsoft</Button>
        </>
      )}

      {state === 'failed' && (
        <>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink-900">
            You don’t have access
          </h1>
          <p className="text-sm text-ink-500">
            You signed in successfully, but this deployment doesn’t accept your account. If this is
            a company install, ask whoever administers it to grant you access.
          </p>
          <Button variant="secondary" onClick={() => void signIn()}>
            Try a different account
          </Button>
        </>
      )}

      {user && <p className="font-mono text-xs text-ink-500">{user.username}</p>}
    </main>
  )
}
