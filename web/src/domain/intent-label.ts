const LABELS: Record<string, string> = {
  title_card: 'Title Card',
  bullet_list: 'Bullet List',
  comparison: 'Comparison',
  diagram_flow: 'Diagram Flow',
  code_walkthrough: 'Code Walkthrough',
  stat_callout: 'Stat Callout',
}

function toTitleCase(raw: string): string {
  return raw
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0]!.toUpperCase() + word.slice(1))
    .join(' ')
}

/** A `VisualIntent` the backend has not been taught to this file yet still renders as a
 * readable label instead of the raw snake_case wire value or a blank. */
export function describeIntent(raw: string): string {
  return LABELS[raw] ?? toTitleCase(raw)
}
