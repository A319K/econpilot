import type { ReactNode } from "react"

const INPUT_CLASS =
  "border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg) " +
  "focus:border-(--color-accent) focus:outline-none disabled:opacity-50"

const INVALID_CLASS = "border-(--color-status-rejected)"

interface FieldShellProps {
  label: string
  hint?: string
  error?: string
  className?: string
  children: ReactNode
}

/** Label + optional hint + optional inline error, wrapped around a control. */
export function FieldShell({ label, hint, error, className = "", children }: FieldShellProps) {
  return (
    <label className={`flex flex-col gap-1 text-xs ${className}`}>
      <span className="text-(--color-fg-dim)">{label}</span>
      {children}
      {error ? (
        <span className="text-(--color-status-rejected)">{error}</span>
      ) : hint ? (
        <span className="text-(--color-fg-faint)">{hint}</span>
      ) : null}
    </label>
  )
}

interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  error?: string
  placeholder?: string
  type?: "text" | "email" | "tel" | "url"
  className?: string
}

export function TextField({
  label,
  value,
  onChange,
  hint,
  error,
  placeholder,
  type = "text",
  className,
}: TextFieldProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={className}>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`${INPUT_CLASS} ${error ? INVALID_CLASS : ""}`}
      />
    </FieldShell>
  )
}

const MONTH_RE = /^\d{4}-\d{2}$/

/**
 * A YYYY-MM date. Renders the browser's native month picker so nobody has to
 * guess the format — but falls back to a plain text box if the stored value
 * isn't a clean YYYY-MM (e.g. someone typed "Present"), so hand-edited
 * profile.yaml values are never silently destroyed by the editor.
 */
export function MonthField({
  label,
  value,
  onChange,
  hint,
  error,
  className,
}: Omit<TextFieldProps, "type" | "placeholder">) {
  const isMonth = value === "" || MONTH_RE.test(value)
  return (
    <FieldShell
      label={label}
      hint={hint ?? (isMonth ? undefined : "free text — clear it to use the date picker")}
      error={error}
      className={className}
    >
      <input
        type={isMonth ? "month" : "text"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${INPUT_CLASS} ${error ? INVALID_CLASS : ""}`}
      />
    </FieldShell>
  )
}

interface SelectFieldProps {
  label: string
  value: string
  options: readonly { value: string; label: string }[]
  onChange: (value: string) => void
  hint?: string
  className?: string
}

export function SelectField({ label, value, options, onChange, hint, className }: SelectFieldProps) {
  return (
    <FieldShell label={label} hint={hint} className={className}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT_CLASS}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}

export function CheckboxField({
  label,
  value,
  onChange,
  hint,
}: {
  label: string
  value: boolean
  onChange: (value: boolean) => void
  hint?: string
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="flex items-center gap-2 text-(--color-fg)">
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
          className="accent-(--color-accent)"
        />
        {label}
      </span>
      {hint ? <span className="text-(--color-fg-faint) pl-5">{hint}</span> : null}
    </label>
  )
}

/**
 * A list of short strings edited as one-per-line text. Far friendlier than
 * asking someone to manage YAML list syntax, and it round-trips cleanly:
 * blank lines are dropped on the way out.
 */
export function LinesField({
  label,
  value,
  onChange,
  hint,
  rows = 4,
  className,
}: {
  label: string
  value: string[]
  onChange: (value: string[]) => void
  hint?: string
  rows?: number
  className?: string
}) {
  return (
    <FieldShell label={label} hint={hint ?? "one per line"} className={className}>
      <textarea
        rows={rows}
        value={(value ?? []).join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
        className={`${INPUT_CLASS} resize-y font-mono`}
      />
    </FieldShell>
  )
}
