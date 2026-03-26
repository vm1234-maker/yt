import { z } from 'zod'
import { NextResponse } from 'next/server'

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
  const res = await fetch(`${process.env.BACKEND_URL}/api/run-agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsed.data),
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
