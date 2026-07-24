import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-moss-600 text-paper-raised hover:bg-moss-700 border border-moss-700',
  secondary:
    'bg-paper-raised text-ink hover:bg-moss-50 border border-hairline-strong',
  ghost:
    'bg-transparent text-ink-soft hover:bg-moss-50 hover:text-ink border border-transparent',
  danger:
    'bg-transparent text-critical hover:bg-red-50 border border-transparent',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium
        transition-colors disabled:cursor-not-allowed disabled:opacity-50
        ${variantClasses[variant]} ${className}`}
      {...props}
    />
  )
}
