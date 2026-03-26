import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// Server-only — service role key, full access, never sent to the browser
// Lazy init so `next build` can load modules when env is missing (e.g. CI without secrets).

let _admin: SupabaseClient | null = null

export function getSupabaseAdmin(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return null
  if (!_admin) _admin = createClient(url, key)
  return _admin
}
