import type { ButtonHTMLAttributes } from "react"

type Variant = "primary" | "ghost" | "danger"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    "border-(--color-accent) text-(--color-accent) hover:bg-(--color-accent-bg) disabled:opacity-40 disabled:hover:bg-transparent",
  ghost:
    "border-(--color-border) text-(--color-fg) hover:border-(--color-fg-dim) hover:text-(--color-fg-bright) disabled:opacity-40",
  danger:
    "border-(--color-status-rejected) text-(--color-status-rejected) hover:bg-red-950/30 disabled:opacity-40",
}

export function Button({ variant = "ghost", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`border px-3 py-1.5 text-xs font-medium tracking-wide transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className}`}
      {...props}
    />
  )
}
