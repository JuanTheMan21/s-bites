import { API_BASE_URL } from '@/api/base-url'
import { authEnabled, loginRequest, msalInstance } from '@/auth/config'
import { closeSession, openSession } from '@/auth/token'
import type { SignedInUser } from '@/domain/user'

/** The UI's only door to authentication.
 *
 * `features/`, `components/` and `routes/` may not import `src/api/*` (ESLint's
 * `no-restricted-imports`), and `src/auth/` reaches into `src/api/` for the base URL -- so the
 * same seam that applies to job data applies here: components talk to this module, and this
 * module talks to MSAL and the API. Exactly the role `stage-adapter.ts` plays for SSE.
 */

export { authEnabled }

export function currentUser(): SignedInUser | null {
  if (!authEnabled) return { name: 'Local Development', username: 'dev@local', accountId: 'dev' }
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
  if (!account) return null
  return {
    name: account.name ?? account.username,
    username: account.username,
    accountId: account.homeAccountId,
  }
}

export async function signIn(): Promise<void> {
  await msalInstance.loginRedirect(loginRequest)
}

export async function signOut(): Promise<void> {
  // Order matters: drop the API's own cookie first, then Entra. Doing it the other way round
  // leaves a valid session cookie behind if the redirect completes before the fetch does, and
  // that cookie alone is enough to keep every media and SSE URL working.
  await closeSession(API_BASE_URL)
  await msalInstance.logoutRedirect()
}

/** Called once after MSAL settles, before the app renders anything that fetches. Establishes the
 * cookie the header-less URLs depend on -- without it, video, subtitles, SCORM and the live
 * progress stream would all 401 while ordinary REST calls worked, which is a confusing way for
 * this to fail. */
export async function establishSession(): Promise<void> {
  if (!authEnabled) return
  await openSession(API_BASE_URL)
}
