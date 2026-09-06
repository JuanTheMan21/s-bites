import { InteractionRequiredAuthError } from '@azure/msal-browser'
import { authEnabled, loginRequest, msalInstance } from './config'

/** Acquiring an access token, and turning it into the API session cookie.
 *
 * Two credentials exist deliberately, and they are not redundant:
 *
 *  - The **bearer token** authenticates JSON/REST calls (`api/client.ts`).
 *  - The **session cookie** authenticates the seven URLs that physically cannot carry a header:
 *    `EventSource`, `<video src>`, `<img src>`, `<a href download>`. See `api/auth.py`.
 *
 * So a signed-in session needs both, and `openSession()` is what establishes the second.
 */

/** A token for the API's own scope, refreshed silently when it can be. Returns `null` when auth
 * is switched off (`AUTH_ENV=none` on the backend) or nobody is signed in -- callers treat that
 * as "send no Authorization header" rather than an error, which is what makes the no-auth local
 * path work through exactly the same code. */
export async function getAccessToken(): Promise<string | null> {
  if (!authEnabled) return null
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
  if (!account) return null
  try {
    const result = await msalInstance.acquireTokenSilent({ ...loginRequest, account })
    return result.accessToken
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      // Consent revoked, password changed, MFA now required -- none of which this call can
      // resolve. Redirecting is the only real fix, and it returns the user to where they were.
      await msalInstance.acquireTokenRedirect({ ...loginRequest, account })
      return null
    }
    throw error
  }
}

/** Exchange the bearer token for the API's `HttpOnly` session cookie.
 *
 * `credentials: 'include'` is required on both this call and every later cookie-authenticated
 * one: the deployed frontend and API are different origins, and a browser sends no cookie
 * cross-origin without it. The backend's CORS already allows credentials, and must name an exact
 * origin rather than `*` for that to be honoured.
 */
export async function openSession(baseUrl: string): Promise<void> {
  const token = await getAccessToken()
  if (!token) return
  const response = await fetch(`${baseUrl}/auth/session`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'include',
  })
  if (!response.ok) {
    throw new Error(`could not open an API session (${response.status})`)
  }
}

export async function closeSession(baseUrl: string): Promise<void> {
  // Best-effort: signing out of Entra below is the part that actually matters, and a failed
  // cookie clear must not block it. The cookie is short-lived and expires on its own regardless.
  try {
    await fetch(`${baseUrl}/auth/session`, { method: 'DELETE', credentials: 'include' })
  } catch {
    // ignored on purpose -- see above
  }
}
