import createClient from 'openapi-fetch'
import { getAccessToken } from '../auth/token'
import { API_BASE_URL } from './base-url'
import type { paths } from './schema'

/** The one `openapi-fetch` client instance in the app. */
export const apiClient = createClient<paths>({ baseUrl: API_BASE_URL })

/** Every JSON/REST call carries the bearer token (T38A). The single `createClient` call above is
 * the only construction site in the app, so this middleware is genuinely the only place a token
 * has to be attached for the whole typed surface.
 *
 * `getAccessToken()` returning `null` is not a failure -- it is the `AUTH_ENV=none` local path,
 * where the request goes out unauthenticated and the backend supplies a development principal.
 * The alternative (a separate unauthenticated client) would mean two transport paths that could
 * drift apart. */
apiClient.use({
  async onRequest({ request }) {
    const token = await getAccessToken()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
})
