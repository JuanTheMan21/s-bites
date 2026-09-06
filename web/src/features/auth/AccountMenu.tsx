import { authEnabled, currentUser, signOut } from '@/adapters/auth-adapter'
import { Button } from '@/components/Button'

/** Who you are signed in as, and how to stop being. Renders nothing when authentication is off,
 * so the local `AUTH_ENV=none` shell looks exactly as it always has. */
export function AccountMenu() {
  const user = authEnabled ? currentUser() : null
  if (!user) return null
  return (
    <div className="flex items-center gap-3">
      <span
        className="hidden max-w-[16ch] truncate font-mono text-xs text-ink-500 sm:inline"
        title={user.username}
      >
        {user.username}
      </span>
      <Button variant="secondary" onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  )
}
