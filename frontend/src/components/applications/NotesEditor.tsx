import { useEffect, useRef, useState } from "react"
import { useUpdateApplicationNotes } from "../../hooks/useApplications"

const DEBOUNCE_MS = 800

export function NotesEditor({ applicationId, notes }: { applicationId: number; notes: string | null }) {
  const [draft, setDraft] = useState(notes ?? "")
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle")
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const updateNotes = useUpdateApplicationNotes()

  useEffect(() => {
    setDraft(notes ?? "")
  }, [applicationId, notes])

  function handleChange(value: string) {
    setDraft(value)
    setStatus("idle")
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setStatus("saving")
      updateNotes.mutate(
        { id: applicationId, payload: { notes: value } },
        { onSuccess: () => setStatus("saved") },
      )
    }, DEBOUNCE_MS)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <div className="flex flex-col gap-1">
      <textarea
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        rows={4}
        placeholder="freeform notes…"
        className="border border-(--color-border) bg-(--color-bg-inset) text-(--color-fg) placeholder:text-(--color-fg-faint) w-full resize-y p-2 text-xs leading-relaxed"
      />
      <span className="text-(--color-fg-faint) text-[10px] tabular-nums">
        {status === "saving" ? "saving…" : status === "saved" ? "saved" : " "}
      </span>
    </div>
  )
}
