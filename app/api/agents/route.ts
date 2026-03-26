import { NextResponse } from 'next/server'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export async function GET() {
  const admin = getSupabaseAdmin()
  if (!admin) {
    return NextResponse.json({ error: 'Supabase is not configured' }, { status: 503 })
  }
  const { data: runs } = await admin
    .from('agent_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(300)

  return NextResponse.json(runs ?? [])
}
