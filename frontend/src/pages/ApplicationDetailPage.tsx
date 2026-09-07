import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { ApiError } from "../api/client"
import type { ApplicationStatus } from "../api/types"
import { ALLOWED_TRANSITIONS } from "../api/types"
import { AutofillPanel } from "../components/applications/AutofillPanel"
import { CoverLetterPanel } from "../components/applications/CoverLetterPanel"
import { NotesEditor } from "../components/applications/NotesEditor"
import { StatusTimeline } from "../components/applications/StatusTimeline"
import { StatusTransitionPanel } from "../components/applications/StatusTransitionPanel"
import { Button } from "../components/ui/Button"
import { Panel } from "../components/ui/Panel"
import { ScoreBar } from "../components/ui/ScoreBar"
import { StatusTag } from "../components/ui/StatusTag"
import { useToast } from "../components/ui/Toast"
import { useApplication, useDeleteApplication, useUpdateApplicationStatus } from "../hooks/useApplications"
import { useJobKeywords } from "../hooks/useJobKeywords"
import { useMode } from "../lib/mode"

const DELETABLE_STATUSES: ApplicationStatus[] = ["discovered", "queued", "withdrawn"]

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable
}

export function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const applicationId = id ? Number(id) : undefined
  const [mode] = useMode()
  const navigate = useNavigate()
  const { push } = useToast()
  const [note, setNote] = useState("")

  const applicationQuery = useApplication(applicationId)
  const keywordsQuery = useJobKeywords(applicationQuery.data?.job_id)
  const updateStatus = useUpdateApplicationStatus()
  const deleteApplication = useDeleteApplication()

  const application = applicationQuery.data

  function attemptTransition(target: ApplicationStatus, force = false) {
    if (!applicationId) return
    updateStatus.mutate(
      { id: applicationId, payload: { status: target, note: note || undefined, force } },
      {
        onSuccess: () => setNote(""),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            push({
              tone: "error",
              message: `Can't move to ${target}: ${error.detail}`,
              action: { label: "Force move anyway", onClick: () => attemptTransition(target, true) },
            })
          } else {
            push({ tone: "error", message: `Transition failed: ${error.message}` })
          }
        },
      },
    )
  }

  useEffect(() => {
    if (!application) return

    function handler(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return
      const digit = Number(e.key)
      if (!Number.isNaN(digit) && digit >= 1 && digit <= 9) {
        const options = ALLOWED_TRANSITIONS[application!.status]
        const target = options[digit - 1]
        if (target) attemptTransition(target)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [application, note])

  if (applicationQuery.isLoading) {
    return <p className="text-(--color-fg-dim) p-4 text-xs">loading…</p>
  }
  if (applicationQuery.isError || !application) {
    return (
      <div className="p-4">
        <p className="text-(--color-status-rejected) text-xs">Application not found.</p>
        <Button variant="ghost" className="mt-2" onClick={() => navigate(`/pipeline?mode=${mode}`)}>
          ← back to pipeline
        </Button>
      </div>
    )
  }

  const canDelete = DELETABLE_STATUSES.includes(application.status)
  const keywords = keywordsQuery.data?.jd_keywords

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-(--color-border) px-4 py-3">
        <div>
          <Button variant="ghost" onClick={() => navigate(`/pipeline?mode=${mode}`)}>
            ← back
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <StatusTag status={application.status} />
          <Button
            variant="danger"
            disabled={!canDelete || deleteApplication.isPending}
            title={canDelete ? "delete application" : "can only delete while discovered/queued/withdrawn"}
            onClick={() => {
              if (!applicationId) return
              deleteApplication.mutate(applicationId, {
                onSuccess: () => navigate(`/pipeline?mode=${mode}`),
                onError: (error) => push({ tone: "error", message: `Delete failed: ${error.message}` }),
              })
            }}
          >
            delete
          </Button>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-2 gap-3 overflow-y-auto p-3">
        <div className="flex flex-col gap-3">
          <Panel title="JOB">
            <h2 className="text-(--color-fg-bright) text-sm font-semibold">{application.job.title}</h2>
            <p className="text-(--color-fg-dim) mt-0.5 text-xs">
              {application.job.location ?? "location unknown"} · {application.job.job_family} ·{" "}
              {application.job.role_type}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <ScoreBar score={application.job.score} />
              <a
                href={application.job.url}
                target="_blank"
                rel="noreferrer"
                className="text-(--color-accent) text-xs hover:underline"
              >
                view posting ↗
              </a>
            </div>

            {keywords && (
              <div className="mt-3 flex flex-wrap gap-1">
                {[...new Set(Object.values(keywords).flat())].map((kw) => (
                  <span
                    key={kw}
                    className="border border-(--color-border) text-(--color-fg-dim) px-1.5 py-0.5 text-[10px]"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="RESUME">
            {application.resume_version ? (
              <div className="flex items-center justify-between text-xs">
                <span className="text-(--color-fg)">{application.resume_version.name}</span>
                {application.resume_version.pdf_path ? (
                  <span className="text-(--color-fg-dim)">{application.resume_version.pdf_path}</span>
                ) : (
                  <span className="text-(--color-fg-faint)">not compiled</span>
                )}
              </div>
            ) : (
              <p className="text-(--color-fg-dim) text-xs">
                no resume attached yet - run Prepare from the Queue view.
              </p>
            )}
          </Panel>

          <Panel title="NOTES">
            <NotesEditor applicationId={application.id} notes={application.notes} />
          </Panel>
        </div>

        <div className="flex flex-col gap-3">
          <Panel title="TRANSITION STATUS">
            <StatusTransitionPanel
              currentStatus={application.status}
              note={note}
              onNoteChange={setNote}
              onTransition={attemptTransition}
              pending={updateStatus.isPending}
            />
          </Panel>

          <Panel title="AUTOFILL">
            <AutofillPanel application={application} />
          </Panel>

          <Panel title="COVER LETTER">
            {application.cover_letter ? (
              <CoverLetterPanel
                coverLetterId={application.cover_letter.id}
                content={application.cover_letter.content}
                needsReview={application.cover_letter.needs_review}
                applicationId={application.id}
              />
            ) : (
              <p className="text-(--color-fg-dim) text-xs">
                no cover letter yet - run Prepare from the Queue view.
              </p>
            )}
          </Panel>

          <Panel title="HISTORY">
            <StatusTimeline history={application.status_history} />
          </Panel>
        </div>
      </div>
    </div>
  )
}
