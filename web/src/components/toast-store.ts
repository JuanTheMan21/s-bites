import { create } from 'zustand'

interface Toast {
  id: number
  message: string
  tone: 'neutral' | 'bad'
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, tone?: Toast['tone']) => void
  dismiss: (id: number) => void
}

let nextId = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, tone = 'neutral') =>
    set((state) => ({ toasts: [...state.toasts, { id: nextId++, message, tone }] })),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))
