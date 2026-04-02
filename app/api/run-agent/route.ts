import { z } from 'zod'
import { NextResponse } from 'next/server'
import { getBackendOrigin } from '@/lib/backend-url'
import { parseBackendProxyBody } from '@/lib/backend-proxy-body'

export const runtime = 'nodejs'

const schema = z.object({
  agent: z.enum([
    'strategy',
    'research',
    'content',
    'production',
    'upload',
    'analytics',
    'brainstorm',
    'setup',
    'nemoclaw',
  ]),
  input: z.any().optional().default({}),
})

export async function POST(request: Request) {
  try {
    let body: unknown
    try {
      body = await request.json()
    } catch {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
    }

    const parsed = schema.safeParse(body)
    if (!parsed.success) {
      return NextResponse.json({ error: parsed.error.flatten() }, { status: 400 })
    }

    const origin = getBackendOrigin()
    if (!origin) {
      return NextResponse.json(
        { error: 'BACKEND_URL is not set on this deployment (Vercel → Environment Variables)' },
        { status: 503 }
      )
    }

    const res = await fetch(`${origin}/api/run-agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed.data),
    })
    const text = await res.text()
    const parsedBody = parseBackendProxyBody(res, text)
    if (!parsedBody.ok) return parsedBody.response
    return NextResponse.json(parsedBody.data, { status: res.status })
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    console.error('[api/run-agent]', e)
    return NextResponse.json({ error: 'run-agent route failed', detail: message }, { status: 500 })
  }
}
