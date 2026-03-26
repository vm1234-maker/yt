import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function GET() {
  const { data: runs } = await supabaseAdmin
    .from('agent_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(300)

  return NextResponse.json(runs ?? [])
}
