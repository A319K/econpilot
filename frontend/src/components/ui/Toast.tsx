import { createContext, useCallback, useContext, useState, type ReactNode } from "react"

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ToastItem {
  id: number
  tone: "error" | "info" | "success"
  message: string
  action?: ToastAction
}

interface ToastContextValue {
  push: (toast: Omit<ToastItem, "id">) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const push = useCallback((toast: Omit<ToastItem, "id">) => {
    const id = nextId++
    setToasts((prev) => [...prev, { ...toast, id }])
    if (toast.tone !== "error") {
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
    }
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toneColor: Record<ToastItem["tone"], string> = {
    error: "var(--color-status-rejected)",
    info: "var(--color-status-in-progress)",
    success: "var(--color-accent)",
  }

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-96 max-w-[92vw] flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="alert"
            className="border bg-(--color-bg-raised) p-3 text-xs shadow-lg"
            style={{ borderColor: toneColor[toast.tone] }}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-(--color-fg-bright) leading-relaxed">{toast.message}</p>
              <button
                onClick={() => dismiss(toast.id)}
                className="text-(--color-fg-dim) hover:text-(--color-fg-bright) shrink-0"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
            {toast.action && (
              <button
                onClick={() => {
                  toast.action?.onClick()
                  dismiss(toast.id)
                }}
                className="mt-2 border border-(--color-accent) px-2 py-1 text-(--color-accent) hover:bg-(--color-accent-bg)"
              >
                {toast.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error("useToast must be used within a ToastProvider")
  return ctx
}
