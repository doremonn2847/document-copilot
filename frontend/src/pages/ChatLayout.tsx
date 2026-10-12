import { useCallback, useState } from 'react'
import { Outlet } from 'react-router-dom'
import ThreadSidebar from '@/components/chat/ThreadSidebar'

export type ChatLayoutContext = { onSaved: () => void }

export default function ChatLayout() {
  const [revision, setRevision] = useState(0)
  const onSaved = useCallback(() => setRevision((value) => value + 1), [])
  return (
    <div className="flex h-dvh flex-col bg-background text-foreground md:flex-row">
      <ThreadSidebar revision={revision} />
      <main className="min-h-0 min-w-0 flex-1"><Outlet context={{ onSaved } satisfies ChatLayoutContext} /></main>
    </div>
  )
}
