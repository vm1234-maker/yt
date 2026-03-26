/**
 * NEXT_PUBLIC_* / server env often omits the scheme. fetch() requires an absolute URL with https.
 */
export function getBackendOrigin(): string | null {
  const raw = process.env.BACKEND_URL?.trim()
  if (!raw) return null
  const noTrailing = raw.replace(/\/+$/, '')
  if (/^https?:\/\//i.test(noTrailing)) return noTrailing
  return `https://${noTrailing}`
}
