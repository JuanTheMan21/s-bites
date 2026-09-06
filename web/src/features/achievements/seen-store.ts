import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { currentUser } from '@/adapters/auth-adapter'

interface SeenState {
  acknowledgedIds: string[]
  acknowledge: (id: string) => void
}

/** Client-side only, `localStorage`-persisted. Every milestone is derivable from `GET /jobs`
 * alone, so a backend achievements endpoint would be real scope (~80 lines + storage + tests)
 * for a cosmetic feature.
 *
 * T38A answered "whose achievements are these", which this file used to note had no answer at
 * all. It is still deliberately *not* server-side -- the question was never the blocker, the cost
 * was -- but the storage key is now scoped per account, so two people signing in on one machine
 * no longer inherit each other's "already celebrated" state. That was previously impossible to
 * even notice, since there was only ever one anonymous user.
 *
 * Keyed on MSAL's `accountId`, not the backend's `owner_id`: this is browser-local state, the
 * frontend is deliberately never told its own owner id (`domain/user.ts`), and `accountId` is
 * already stable per account per browser, which is exactly the scope of the thing being stored.
 */
function storageKey(): string {
  const account = currentUser()
  return account ? `s-bites-milestones:${account.accountId}` : 's-bites-milestones'
}

export const useSeenMilestones = create<SeenState>()(
  persist(
    (set) => ({
      acknowledgedIds: [],
      acknowledge: (id) =>
        set((state) =>
          state.acknowledgedIds.includes(id)
            ? state
            : { acknowledgedIds: [...state.acknowledgedIds, id] },
        ),
    }),
    { name: storageKey() },
  ),
)
