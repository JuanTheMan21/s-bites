/** Shared between `client.ts` (fetch) and `artifact-urls.ts` (plain `<a href>`/`<video src>`
 * targets, which never go through `openapi-fetch` since their responses aren't JSON).
 *
 * Defaults to `/api` rather than `''`. The backend's own routes (`/jobs`, `/jobs/{id}`) are
 * identical strings to this app's own client-side routes (`routes/DashboardPage.tsx`,
 * `routes/StudioPage.tsx`'s `/jobs/:jobId`) -- a bare-`/jobs` dev proxy would intercept a real browser
 * navigation to the frontend's `/jobs` page before React Router ever saw it, returning raw JSON
 * instead of the app. `vite.config.ts`'s proxy strips this `/api` prefix before forwarding, so
 * the backend's own route paths never have to know this exists. In production, `VITE_API_BASE`
 * is set to the deployed backend's absolute origin -- a different origin entirely, so the
 * collision this exists to avoid cannot happen there regardless. */
export const API_BASE_URL = import.meta.env.VITE_API_BASE || '/api'
