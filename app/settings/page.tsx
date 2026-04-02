import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Settings — NemoClaw',
}

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1
          className="text-2xl font-bold tracking-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          Settings
        </h1>
        <p className="text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
          The <code className="mono text-xs">settings?_rsc=…</code> requests in DevTools are Next.js
          loading this page&apos;s server payload — not your API. A 404 there only meant this route
          was missing before; it does not indicate whether an agent run succeeded.
        </p>
      </div>

      <div
        className="rounded-lg p-4 text-sm space-y-3"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
        }}
      >
        <p style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Where things run:</strong> Secrets and{' '}
          <code className="mono text-xs">BACKEND_URL</code> live in Vercel and Railway env vars. The
          dashboard talks to your deployed API; agent work runs on the Celery worker (typically
          Railway).
        </p>
        <p style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Did a run work?</strong> Open{' '}
          <a href="/agents" className="underline underline-offset-2" style={{ color: 'var(--amber)' }}>
            Agents
          </a>{' '}
          and check the latest row: <span className="mono text-xs">success</span>,{' '}
          <span className="mono text-xs">running</span>, or <span className="mono text-xs">error</span>.
        </p>
      </div>
    </div>
  )
}
