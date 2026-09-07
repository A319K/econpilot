import { useRef, useState } from "react"
import { ApiError } from "../../api/client"
import { JOB_FAMILIES, type JobFamily, type ResumeVersion } from "../../api/types"
import { useUploadResume } from "../../hooks/useResumes"
import { Button } from "../ui/Button"

/** Strip the extension so "Finance Resume v3.pdf" becomes a sensible default name. */
function nameFromFile(filename: string): string {
  return filename.replace(/\.pdf$/i, "").trim()
}

/**
 * Drag-and-drop for a finished resume PDF.
 *
 * Our users keep 2-3 resumes aimed at different kinds of role and already have
 * them as PDFs — this is how those get in, without a LaTeX toolchain.
 */
export function ResumeUpload({ onUploaded }: { onUploaded?: (resume: ResumeVersion) => void }) {
  const uploadResume = useUploadResume()
  const inputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [jobFamily, setJobFamily] = useState<JobFamily>("data")
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function accept(selected: File | undefined) {
    setError(null)
    if (!selected) return
    if (!selected.name.toLowerCase().endsWith(".pdf")) {
      setError("That needs to be a PDF. In Word or Google Docs, use File → Download → PDF.")
      return
    }
    setFile(selected)
    if (!name.trim()) setName(nameFromFile(selected.name))
  }

  function handleUpload() {
    if (!file) return
    const trimmed = name.trim() || nameFromFile(file.name)
    uploadResume.mutate(
      { file, name: trimmed, jobFamily },
      {
        onSuccess: (resume) => {
          setFile(null)
          setName("")
          setError(null)
          if (inputRef.current) inputRef.current.value = ""
          onUploaded?.(resume)
        },
        onError: (err) =>
          setError(
            err instanceof ApiError ? err.detail : "Couldn't upload that file. Is the backend running?",
          ),
      },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          accept(e.dataTransfer.files[0])
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center gap-1 border border-dashed px-3 py-6 text-center text-xs transition-colors ${
          dragging
            ? "border-(--color-accent) bg-(--color-accent-bg) text-(--color-accent)"
            : "border-(--color-border) text-(--color-fg-dim) hover:border-(--color-fg-dim)"
        }`}
      >
        <span className="text-(--color-fg-bright)">
          {file ? file.name : "Drag your resume PDF here"}
        </span>
        <span className="text-(--color-fg-faint)">
          {file ? "drop another to replace it" : "or click to pick a file — PDF, up to 10 MB"}
        </span>
      </div>

      {/* The same action for anyone who'd rather not drag, and for keyboards. */}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        onChange={(e) => accept(e.target.files?.[0])}
        className="sr-only"
        aria-label="Choose a resume PDF"
      />

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">what to call it</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Finance / IB"
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">use it for</span>
          <select
            value={jobFamily}
            onChange={(e) => setJobFamily(e.target.value as JobFamily)}
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          >
            {JOB_FAMILIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <Button variant="primary" onClick={handleUpload} disabled={!file || uploadResume.isPending}>
          {uploadResume.isPending ? "uploading…" : "add this resume"}
        </Button>
      </div>

      <p className="text-(--color-fg-faint) text-xs">
        EconPilot picks whichever of your resumes best fits each job, so add one per kind of role
        you're going for.
      </p>

      {error ? <p className="text-(--color-status-rejected) text-xs">{error}</p> : null}
    </div>
  )
}
