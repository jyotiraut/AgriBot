import { useEffect, useRef, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createChatSession,
  deleteChatSession,
  getChatSessionMessages,
  listChatSessions,
  sendChatMessage,
} from '@/lib/api'
import type { ChatMessageOut } from '@/lib/types'
import { useUi } from '@/lib/ui'
import { ChatSessionSidebar } from '@/components/chat/ChatSessionSidebar'
import { MessageBubble } from '@/components/chat/MessageBubble'

function SidebarToggleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M9.5 4.5v15" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export const Route = createFileRoute('/_app/chat')({
  component: ChatPage,
})

function ChatPage() {
  const queryClient = useQueryClient()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [localMessages, setLocalMessages] = useState<ChatMessageOut[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const sidebarOpen = useUi((s) => s.chatSidebarOpen)
  const setSidebarOpen = useUi((s) => s.setChatSidebarOpen)

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: listChatSessions,
  })

  // Default to the most recent session once the list loads.
  useEffect(() => {
    if (!activeId && sessionsQuery.data && sessionsQuery.data.length > 0) {
      setActiveId(sessionsQuery.data[0].id)
    }
  }, [sessionsQuery.data, activeId])

  const messagesQuery = useQuery({
    queryKey: ['chat-messages', activeId],
    queryFn: () => getChatSessionMessages(activeId!),
    enabled: !!activeId,
  })

  useEffect(() => {
    setLocalMessages(messagesQuery.data ?? [])
  }, [messagesQuery.data])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [localMessages])

  const newSessionMutation = useMutation({
    mutationFn: createChatSession,
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      setActiveId(session.id)
      setLocalMessages([])
    },
  })

  const deleteSessionMutation = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (deletedId === activeId) setActiveId(null)
    },
  })

  const sendMutation = useMutation({
    mutationFn: ({ text, sessionId }: { text: string; sessionId?: string }) =>
      sendChatMessage(text, sessionId),
    onSuccess: (res) => {
      setActiveId(res.session_id)
      setLocalMessages((prev) => [
        ...prev,
        { role: 'assistant', message: res.reply, timestamp: new Date().toISOString() },
      ])
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
    onError: () => {
      setLocalMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          message: 'Something went wrong reaching the server. Please try again.',
          timestamp: new Date().toISOString(),
        },
      ])
    },
  })

  function onSend() {
    const text = draft.trim()
    if (!text || sendMutation.isPending) return
    setLocalMessages((prev) => [
      ...prev,
      { role: 'user', message: text, timestamp: new Date().toISOString() },
    ])
    setDraft('')
    sendMutation.mutate({ text, sessionId: activeId ?? undefined })
  }

  const sessions = sessionsQuery.data ?? []
  const activeSession = sessions.find((s) => s.id === activeId)

  return (
    <div className="flex h-full">
      <ChatSessionSidebar
        sessions={sessions}
        activeId={activeId}
        open={sidebarOpen}
        onSelect={setActiveId}
        onNew={() => newSessionMutation.mutate()}
        onDelete={(id) => deleteSessionMutation.mutate(id)}
        isCreating={newSessionMutation.isPending}
      />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-hairline px-4 py-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title={sidebarOpen ? 'Hide conversations' : 'Show conversations'}
            className="rounded-md p-1.5 text-ink-soft transition-colors hover:bg-moss-50 hover:text-ink"
          >
            <SidebarToggleIcon className="h-5 w-5" />
          </button>
          <h1 className="truncate text-sm font-medium text-ink">
            {activeSession?.title ?? 'New chat'}
          </h1>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {localMessages.length === 0 && !messagesQuery.isLoading && (
              <div className="mt-16 text-center text-ink-muted">
                <p className="text-3xl">🌾</p>
                <p className="mt-2 text-sm">
                  Ask about planting, prices, weather, or what to harvest this month.
                </p>
              </div>
            )}
            {localMessages.map((m, i) => (
              <MessageBubble key={i} role={m.role} message={m.message} />
            ))}
            {sendMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-ink-muted">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-moss-50">
                  🌾
                </span>
                Thinking…
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-hairline bg-paper-raised p-4">
          <div className="mx-auto flex max-w-2xl items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              rows={1}
              placeholder="Type your question…"
              className="max-h-32 flex-1 resize-none rounded-md border border-hairline-strong bg-paper-raised
                px-3 py-2.5 text-sm text-ink placeholder:text-ink-muted focus:border-moss-500
                focus:outline-none focus:ring-2 focus:ring-moss-100"
            />
            <button
              onClick={onSend}
              disabled={!draft.trim() || sendMutation.isPending}
              className="shrink-0 rounded-md bg-moss-600 px-4 py-2.5 text-sm font-medium text-paper-raised
                transition-colors hover:bg-moss-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
