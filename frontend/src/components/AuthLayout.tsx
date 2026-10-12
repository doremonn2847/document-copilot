import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export default function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-background px-6 py-12 text-foreground sm:py-20">
      <div className="mx-auto max-w-md">
        <Link to="/" className="text-sm font-medium text-muted-foreground underline-offset-4 hover:underline">Document Copilot</Link>
        <h1 className="mt-12 mb-6 text-3xl font-semibold tracking-tight">{title}</h1>
        <div className="space-y-6">{children}</div>
      </div>
    </main>
  )
}
