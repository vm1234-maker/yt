import { z } from 'zod'
import { NextResponse } from 'next/server'
import { getBackendOrigin } from '@/lib/backend-url'

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
  ]),
  input: z.record(z.string(), z.unknown()).optional().default({}),
})

export async function POST(request: Request) {
  const body = await request.json()
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 400 })
  }
  const origin = getBackendOrigin()
  if (!origin) {
    return NextResponse.json(
      { error: 'BACKEND_URL is not set on this deployment (Vercel → Settings → Environment Variables)' },
      { status: 503 }
    )
  }
  try {
    const res = await fetch(`${origin}/api/run-agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed.data),
    })
    const text = await res.text()
    let data: unknown = {}
    try {
      data = text ? JSON.parse(text) : {}
    } catch {
      return NextResponse.json(
        {
          error: 'Backend returned non-JSON',
          backendStatus: res.status,
          snippet: text.slice(0, 400),
        },
        { status: 502 }
      )
    }
    return NextResponse.json(data, { status: res.status })
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ error: 'Failed to reach backend', detail: message }, { status: 502 })
  }
}
