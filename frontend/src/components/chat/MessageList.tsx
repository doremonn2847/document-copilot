import type { UIMessage } from 'ai'

export default function MessageList({ messages, provisional }: { messages: UIMessage[]; provisional: boolean }) {
  return <div className="space-y-6">{messages.map((message, index) => (
    <article key={message.id} className={message.role === 'user' ? 'ml-8 rounded-xl bg-muted p-4' : 'mr-8 p-4'}>
      <p className="mb-2 text-xs font-semibold text-muted-foreground">{message.role === 'user' ? 'You' : 'Document Copilot'}</p>
      <p className="whitespace-pre-wrap break-words">{message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('')}</p>
      {provisional && message.role === 'assistant' && index === messages.length - 1 && <p className="mt-2 text-xs text-muted-foreground">Provisional reply</p>}
    </article>
  ))}</div>
}
