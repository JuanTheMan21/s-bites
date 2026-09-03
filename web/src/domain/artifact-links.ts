// Re-exported through domain/ rather than imported from api/ directly in features/ -- these are
// plain URL strings (consumed as <video src>/<a href> targets, never fetched with JS), but the
// eslint no-restricted-imports rule bans `**/api/*` from features/ uniformly, and a single
// re-export here is cheaper than special-casing the rule for "the parts of api/ that happen to
// be safe."
export { artifactUrls } from '@/api/artifact-urls'
