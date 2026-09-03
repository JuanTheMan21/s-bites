/** Thrown by every function in `api/endpoints.ts` for a non-2xx response. `status` lets a
 * caller branch on a code the OpenAPI schema never documented (404, 409) the same way it
 * branches on a documented one (422) -- FastAPI's `HTTPException` status codes are real and
 * meaningful even when `app.openapi()` has no `responses=` entry for them. */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(action: string, status: number, body: unknown) {
    super(`${action} failed with ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}
