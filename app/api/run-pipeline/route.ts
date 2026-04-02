import { z } from 'zod'
import { NextResponse } from 'next/server'
import { getBackendOrigin } from '@/lib/backend-url'
import { parseBackendProxyBody } from '@/lib/backend-proxy-body'

const schema = z.object({
  input: z.any().optional().default({}),
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
      { error: 'BACKEND_URL is not set on this deployment (Vercel → Environment Variables)' },
      { status: 503 }
    )
  }
  try {
    const res = await fetch(`${origin}/api/run-pipeline`, {
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
    return NextResponse.json({ error: 'Failed to reach backend', detail: message }, { status: 502 })
  }
}
