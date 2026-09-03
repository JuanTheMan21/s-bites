/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute API origin in production; left unset in dev so requests stay relative and hit
   * vite.config.ts's proxy (which forwards to VITE_API_BASE itself, or scripts/serve_fake.py's
   * default port, if this is also unset there). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
