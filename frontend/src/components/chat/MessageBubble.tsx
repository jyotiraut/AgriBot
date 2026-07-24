interface Props {
  role: 'user' | 'assistant'
  message: string
}

export function MessageBubble({ role, message }: Props) {
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] rounded-2xl rounded-tr-sm bg-moss-600 px-4 py-2.5 text-sm text-paper-raised">
          {message}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2.5">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-moss-50 text-sm">
        🌾
      </div>
      <div className="max-w-[70%] whitespace-pre-wrap rounded-2xl rounded-tl-sm border border-hairline bg-paper-raised px-4 py-2.5 text-sm text-ink">
        {message}
      </div>
    </div>
  )
}
