import { NextResponse } from 'next/server'

export async function GET(request: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params
  const res = await fetch(`${process.env.BACKEND_URL}/api/agent-status/${id}`)
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
