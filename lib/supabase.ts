import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// Client-side — anon key, safe to expose, RLS enforced
// Lazy init so `next build` works when env is missing (e.g. CI without secrets).

let _browser: SupabaseClient | null = null

export function getSupabaseBrowser(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  if (!_browser) _browser = createClient(url, key)
  return _browser
}
