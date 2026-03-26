import { createClient } from '@supabase/supabase-js'

// Server-only — service role key, full access, never sent to browser
// Import this ONLY in Server Components, API routes, and Server Actions
export const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)
