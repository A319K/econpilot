import { useEffect, useState } from "react"
import { ApiError } from "../../api/client"
import { useReviewCoverLetter, useUpdateCoverLetter } from "../../hooks/useCoverLetter"
import { Button } from "../ui/Button"
import { useToast } from "../ui/Toast"

export function CoverLetterPanel({
  coverLetterId,
  content,
  needsReview,
  applicationId,
}: {
  coverLetterId: number
  content: string
  needsReview: boolean
  applicationId: number
}) {
  const [draft, setDraft] = useState(content)
  const [editing, setEditing] = useState(false)
  const { push } = useToast()

  useEffect(() => {
    if (!editing) setDraft(content)
  }, [content, editing])

  const updateCoverLetter = useUpdateCoverLetter(applicationId)
  const reviewCoverLetter = useReviewCoverLetter(applicationId)

  function handleSave() {
    updateCoverLetter.mutate(
      { id: coverLetterId, payload: { content: draft } },
      {
        onSuccess: () => {
          setEditing(false)
          push({ tone: "success", message: "Cover letter saved and recompiled." })
        },
        onError: (error) => {
          const message = error instanceof ApiError ? error.detail : error.message
          push({ tone: "error", message: `Save failed: ${message}` })
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {needsReview && (
        <div className="border border-(--color-status-queued) bg-(--color-bg-raised) flex items-center justify-between px-2 py-1.5 text-xs">
          <span className="text-(--color-status-queued)">⚠ needs review</span>
          <Button
            variant="primary"
            disabled={reviewCoverLetter.isPending}
            onClick={() => reviewCoverLetter.mutate({ id: coverLetterId, payload: { reviewed: true } })}
          >
            mark reviewed
          </Button>
        </div>
      )}

      {editing ? (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={12}
            className="border border-(--color-border) bg-(--color-bg-inset) text-(--color-fg) w-full resize-y p-2 text-xs leading-relaxed"
          />
          <div className="flex gap-2">
            <Button variant="primary" onClick={handleSave} disabled={updateCoverLetter.isPending}>
              {updateCoverLetter.isPending ? "saving…" : "save"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setDraft(content)
                setEditing(false)
              }}
            >
              cancel
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="text-(--color-fg) whitespace-pre-wrap text-xs leading-relaxed">{content}</p>
          <Button variant="ghost" onClick={() => setEditing(true)} className="self-start">
            edit
          </Button>
        </>
      )}
    </div>
  )
}
