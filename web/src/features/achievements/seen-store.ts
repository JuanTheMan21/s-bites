import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SeenState {
  acknowledgedIds: string[]
  acknowledge: (id: string) => void
}

/** Client-side only, `localStorage`-persisted. Every milestone is derivable from `GET /jobs`
 * alone, so a backend achievements endpoint would be real scope (~80 lines + storage + tests)
 * for a cosmetic feature -- and there is no auth/user model in this backend at all yet, so "whose
 * achievements are these" has no answer. This store's only job is remembering which milestones
 * this browser has already been shown, so a returning visit doesn't re-celebrate the same one. */
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
    { name: 's-bites-milestones' },
  ),
)
