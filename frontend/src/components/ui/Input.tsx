import type { InputHTMLAttributes, LabelHTMLAttributes } from 'react'

export function Field({ className = '', ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={`mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted ${className}`}
      {...props}
    />
  )
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-md border border-hairline-strong bg-paper-raised px-3 py-2 text-sm
        text-ink placeholder:text-ink-muted focus:border-moss-500 focus:outline-none
        focus:ring-2 focus:ring-moss-100 ${className}`}
      {...props}
    />
  )
}
