'use server'

import { supabaseAdmin } from '@/lib/supabase-admin'
import { revalidatePath } from 'next/cache'

export async function approveContent(id: string): Promise<void> {
  await supabaseAdmin
    .from('content_queue')
    .update({ status: 'approved', approved_at: new Date().toISOString() })
    .eq('id', id)
  revalidatePath('/content')
}

export async function rejectContent(id: string): Promise<void> {
  await supabaseAdmin
    .from('content_queue')
    .update({ status: 'rejected' })
    .eq('id', id)
  revalidatePath('/content')
}
