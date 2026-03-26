import { NextResponse } from 'next/server'
import { getBackendOrigin } from '@/lib/backend-url'

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
