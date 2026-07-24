import type { ReactNode } from 'react'

export function AuthPageFrame({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen w-full items-center justify-center bg-paper px-4">
      <div className="absolute top-6 left-6 flex items-center gap-2">
        <span className="text-xl">🌾</span>
        <span className="font-display text-lg font-semibold text-moss-700">KrishiMitra</span>
      </div>
      {children}
    </div>
  )
}
