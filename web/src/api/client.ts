import createClient from 'openapi-fetch'
import { API_BASE_URL } from './base-url'
import type { paths } from './schema'

/** The one `openapi-fetch` client instance in the app. */
export const apiClient = createClient<paths>({ baseUrl: API_BASE_URL })
