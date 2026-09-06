import { PublicClientApplication, type Configuration } from '@azure/msal-browser'

/** Entra sign-in configuration (T38A).
 *
 * Deliberately a new top-level directory rather than a `features/` one. `eslint.config.js`
 * forbids `features/`, `components/` and `routes/` from importing `src/api/*` or `openapi-fetch`,
 * and the token plumbing has to reach both -- so it lives beside `api/` at the same level, and
 * the UI reaches it through `src/adapters/auth-adapter.ts` like it reaches everything else.
 *
 * `VITE_ENTRA_AUTHORITY` is the one value that decides who may sign in, and it is the whole
 * portability story:
 *   .../common      -- any Microsoft identity, personal or work. What a personal tenant can do.
 *   .../<tenant-id> -- an ordinary single-tenant enterprise app; only that directory signs in.
 * Nothing else changes between the two, here or in the API.
 */

const CLIENT_ID = import.meta.env.VITE_ENTRA_CLIENT_ID ?? ''
const AUTHORITY =
  import.meta.env.VITE_ENTRA_AUTHORITY ?? 'https://login.microsoftonline.com/common'

/** `false` runs the app against a backend with `AUTH_ENV=none`: no sign-in, no MSAL, no tenant.
 * That is the local/offline path, and it stays a first-class mode rather than a broken one. */
export const authEnabled = CLIENT_ID !== ''

/** The scope the API demands (`ENTRA_REQUIRED_SCOPE`). Exposed by the same app registration the
 * SPA signs into, which is why it is `api://<client-id>/...` and not a Graph scope. */
export const apiScope = `api://${CLIENT_ID}/${
  import.meta.env.VITE_ENTRA_SCOPE ?? 'Jobs.ReadWrite'
}`

const configuration: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: AUTHORITY,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    // sessionStorage, not localStorage: the refresh artefacts stay scoped to this tab, so a
    // shared machine does not leave someone else signed in. The API session cookie is HttpOnly
    // and short-lived for the same reason.
    cacheLocation: 'sessionStorage',
  },
}

export const msalInstance = new PublicClientApplication(configuration)

export const loginRequest = { scopes: [apiScope] }
