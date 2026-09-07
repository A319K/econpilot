import { useState } from "react"
import { ApiError } from "../../api/client"
import type { ResumeVersion } from "../../api/types"
import { JOB_FAMILIES, type JobFamily } from "../../api/types"
import { useResumes, useUpdateResume } from "../../hooks/useResumes"
import { type LogLine, ProgressLog } from "../ui/ProgressLog"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import { formatTimestamp } from "../../lib/format"
import { ResumeUpload } from "./ResumeUpload"

export function ResumeLibrary() {
  const resumesQuery = useResumes()
  const updateResume = useUpdateResume()
  const [selected, setSelected] = useState<ResumeVersion | null>(null)
  const [draftSource, setDraftSource] = useState("")
  const [draftFamily, setDraftFamily] = useState<JobFamily>("finance")
  const [log, setLog] = useState<LogLine[]>([])

  function select(resume: ResumeVersion) {
    setSelected(resume)
    setDraftSource(resume.latex_source ?? "")
    setDraftFamily(resume.job_family)
    setLog([])
  }

  function handleSave() {
    if (!selected) return
    const timestamp = formatTimestamp(new Date().toISOString())
    updateResume.mutate(
      { id: selected.id, payload: { latex_source: draftSource, job_family: draftFamily } },
      {
        onSuccess: (updated) => {
          setSelected(updated)
          setLog((prev) => [...prev, { timestamp, text: `compiled → ${updated.pdf_path}`, tone: "success" }])
        },
        onError: (error) => {
          const message = error instanceof ApiError ? error.detail : error.message
          setLog((prev) => [...prev, { timestamp, text: message, tone: "error" }])
        },
      },
    )
  }

  const resumes = resumesQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <ResumeUpload onUploaded={select} />

      <div className="grid grid-cols-[1fr_2fr] gap-3">
      <div className="flex flex-col gap-1.5">
        {resumesQuery.isLoading ? (
          <p className="text-(--color-fg-dim) text-xs">loading…</p>
        ) : resumes.length === 0 ? (
          <EmptyState
            title="No resumes yet"
            hint="Drag a PDF into the box above to add your first one."
          />
        ) : (
          resumes.map((resume) => (
            <button
              key={resume.id}
              onClick={() => select(resume)}
              className={`border px-2 py-1.5 text-left text-xs ${
                selected?.id === resume.id
                  ? "border-(--color-accent) text-(--color-accent)"
                  : "border-(--color-border) text-(--color-fg) hover:border-(--color-fg-dim)"
              }`}
            >
              <div className="truncate font-medium">{resume.name}</div>
              <div className="text-(--color-fg-dim)">
                {resume.job_family} · {resume.is_uploaded ? "uploaded PDF" : resume.is_base_template ? "base" : "tailored"}
              </div>
            </button>
          ))
        )}
      </div>

      {selected && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs">
              <span className="text-(--color-fg-dim)">job family</span>
              <select
                value={draftFamily}
                onChange={(e) => setDraftFamily(e.target.value as JobFamily)}
                className="border border-(--color-border) bg-(--color-bg) px-1 py-0.5 text-(--color-fg)"
              >
                {JOB_FAMILIES.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
            <span className="text-(--color-fg-faint) text-xs">
              {selected.pdf_path ?? "not compiled"}
            </span>
          </div>

          {selected.is_uploaded ? (
            <div className="border border-(--color-border) px-3 py-4 text-xs">
              <p className="text-(--color-fg-bright)">This is a PDF you uploaded.</p>
              <p className="text-(--color-fg-dim) mt-1">
                {selected.original_filename ?? "your file"} — it gets attached to applications exactly
                as it is. To change it, edit the file on your computer and drag the new version in
                above.
              </p>
            </div>
          ) : (
            <>
              <textarea
                value={draftSource}
                onChange={(e) => setDraftSource(e.target.value)}
                rows={16}
                spellCheck={false}
                className="border border-(--color-border) bg-(--color-bg-inset) text-(--color-fg) w-full resize-y p-2 font-mono text-xs leading-relaxed"
              />

              <Button
                variant="primary"
                onClick={handleSave}
                disabled={updateResume.isPending}
                className="self-start"
              >
                {updateResume.isPending ? "compiling…" : "save & recompile"}
              </Button>
            </>
          )}

          {log.length > 0 && <ProgressLog lines={log} />}
        </div>
      )}
      </div>
    </div>
  )
}
