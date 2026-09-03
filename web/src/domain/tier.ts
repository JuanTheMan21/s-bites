export interface TierDescriptor {
  label: string
  /** A CSS custom property name, e.g. `--tier-2`, defined in `index.css`. */
  colorVar: string
}

const TIERS: Record<number, TierDescriptor> = {
  0: { label: 'Static', colorVar: '--tier-0' },
  1: { label: 'Reveal', colorVar: '--tier-1' },
  2: { label: 'Animated', colorVar: '--tier-2' },
}

const UNKNOWN_TIER: TierDescriptor = { label: 'Unknown tier', colorVar: '--ink-500' }

/** `null` (not yet assigned) is distinct from an unrecognised number (a future Tier the
 * backend added) -- the caller decides how to render "not yet earned" vs. "earned something
 * this UI doesn't have a name for," and both degrade rather than crash either way. */
export function describeTier(tier: number | null): TierDescriptor | null {
  if (tier === null) return null
  return TIERS[tier] ?? UNKNOWN_TIER
}
