import { NextResponse } from 'next/server'

/**
 * Parse FastAPI JSON or surface plain-text / HTML errors from the backend (e.g. Railway 503).
 */
export function parseBackendProxyBody(
  res: Response,
  text: string
): { ok: true; data: unknown } | { ok: false; response: NextResponse } {
  const trimmed = text.trim()
  if (!trimmed) {
    if (!res.ok) {
      return {
        ok: false,
        response: NextResponse.json(
          {
            error: `Backend returned ${res.status} with an empty body.`,
            backendStatus: res.status,
          },
          { status: 502 }
        ),
      }
    }
    return { ok: true, data: {} }
  }
  try {
    return { ok: true, data: JSON.parse(text) }
  } catch {
    const snippet = trimmed.slice(0, 280)
    const hint =
      res.status === 503 || res.status === 502
        ? ' Check Railway (or API host): service may be stopped, crashed, or still deploying.'
        : ''
    return {
      ok: false,
      response: NextResponse.json(
        {
          error: `Backend ${res.status}: ${snippet}${hint ? ' ' + hint : ''}`,
          backendStatus: res.status,
          snippet: text.slice(0, 500),
        },
        { status: 502 }
      ),
    }
  }
}
