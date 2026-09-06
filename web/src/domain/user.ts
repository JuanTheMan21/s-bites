/** The signed-in user, as the UI is allowed to know them (T38A).
 *
 * Note what is *not* here: no owner id, no tenant id, no token. Those are the API's business.
 * A component that could see the owner id would eventually be tempted to filter on it, which
 * would mean re-deciding in the browser an authorisation question the backend has already
 * decided — and deciding it wrong, since the browser only ever receives jobs the caller owns
 * in the first place.
 */
export interface SignedInUser {
  /** Display name, falling back to the sign-in name when the token carries no `name` claim. */
  name: string
  /** The sign-in name (`preferred_username`). Human-readable and **not** a stable identifier --
   * it changes when someone renames their account. Display only. */
  username: string
  /** MSAL's own local account key. Stable per account per browser, so it is a safe key for
   * per-user client-side state; it is not the backend's `owner_id` and must never be sent as one.
   */
  accountId: string
}
