import { NextResponse } from 'next/server'
import { getBackendOrigin } from '@/lib/backend-url'
import { parseBackendProxyBody } from '@/lib/backend-proxy-body'

export async function GET(request: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params
  const origin = getBackendOrigin()
  if (!origin) {
    return NextResponse.json(
      { error: 'BACKEND_URL is not set on this deployment (Vercel → Settings → Environment Variables)' },
      { status: 503 }
    )
  }
  try {
    const res = await fetch(`${origin}/api/agent-status/${id}`)
    const text = await res.text()
    const parsedBody = parseBackendProxyBody(res, text)
    if (!parsedBody.ok) return parsedBody.response
    return NextResponse.json(parsedBody.data, { status: res.status })
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ error: 'Failed to reach backend', detail: message }, { status: 502 })
  }
}
