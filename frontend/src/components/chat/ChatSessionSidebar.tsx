import type { ChatSession } from '@/lib/types'

interface Props {
  sessions: ChatSession[]
  activeId: string | null
  open: boolean
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  isCreating: boolean
}

export function ChatSessionSidebar({ sessions, activeId, open, onSelect, onNew, onDelete, isCreating }: Props) {
  return (
    <div
      className={`flex h-full shrink-0 flex-col overflow-hidden border-hairline bg-paper-raised
        transition-[width] duration-200 ease-in-out ${open ? 'w-72 border-r' : 'w-0 border-r-0'}`}
    >
      <div className="w-72 p-3">
        <button
          onClick={onNew}
          disabled={isCreating}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-moss-600
            bg-moss-600 px-3 py-2 text-sm font-medium text-paper-raised transition-colors
            hover:bg-moss-700 disabled:opacity-50"
        >
          <span className="text-base leading-none">+</span> New chat
        </button>
      </div>

      <div className="w-72 flex-1 overflow-y-auto px-2 pb-3">
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-sm text-ink-muted">No conversations yet.</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`group mb-1 flex cursor-pointer items-center justify-between gap-2 rounded-md
              px-3 py-2.5 text-sm transition-colors
              ${s.id === activeId ? 'bg-moss-50 text-moss-700' : 'text-ink-soft hover:bg-paper'}`}
          >
            <span className="truncate">{s.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(s.id)
              }}
              className="shrink-0 text-ink-muted opacity-0 hover:text-critical group-hover:opacity-100"
              title="Delete conversation"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
