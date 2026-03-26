'use server'

import { getSupabaseAdmin } from '@/lib/supabase-admin'
import { revalidatePath } from 'next/cache'

export async function approveContent(id: string): Promise<void> {
  const admin = getSupabaseAdmin()
  if (!admin) throw new Error('Supabase is not configured')
  await admin
    .from('content_queue')
    .update({ status: 'approved', approved_at: new Date().toISOString() })
    .eq('id', id)
  revalidatePath('/content')
}

export async function rejectContent(id: string): Promise<void> {
  const admin = getSupabaseAdmin()
  if (!admin) throw new Error('Supabase is not configured')
  await admin
    .from('content_queue')
    .update({ status: 'rejected' })
    .eq('id', id)
  revalidatePath('/content')
}
