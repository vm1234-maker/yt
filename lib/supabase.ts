import { createClient } from '@supabase/supabase-js'

// Client-side — anon key, safe to expose, RLS enforced
// Import this in 'use client' components and Realtime subscriptions
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
