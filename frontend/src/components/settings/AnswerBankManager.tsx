import { useState } from "react"
import type { AnswerBankEntry } from "../../api/types"
import { useAnswerBank, useCreateAnswer, useDeleteAnswer, useUpdateAnswer } from "../../hooks/useAnswerBank"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import { useToast } from "../ui/Toast"

function AnswerRow({ entry }: { entry: AnswerBankEntry }) {
  const update = useUpdateAnswer()
  const remove = useDeleteAnswer()
  const { push } = useToast()
  const [answer, setAnswer] = useState(entry.answer)
  const dirty = answer !== entry.answer

  const pending = !entry.approved

  return (
    <div
      className={`flex flex-col gap-1.5 border-b border-(--color-border-dim) py-2 ${pending ? "border-l-2 border-l-(--color-accent) pl-2" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-(--color-fg-bright) text-xs font-medium">{entry.question_raw}</span>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-(--color-fg-faint) text-[10px] uppercase">{entry.source}</span>
          {pending ? (
            <span className="text-(--color-accent) border border-(--color-accent) px-1 text-[10px] uppercase">
              suggested
            </span>
          ) : (
            <span className="text-(--color-fg-faint) text-[10px]">used {entry.times_used}×</span>
          )}
        </div>
      </div>

      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        rows={2}
        className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-xs text-(--color-fg)"
      />

      <div className="flex items-center gap-2">
        {pending && (
          <Button
            variant="primary"
            disabled={update.isPending}
            onClick={() =>
              update.mutate(
                { id: entry.id, payload: { approved: true, ...(dirty ? { answer } : {}) } },
                { onError: (e) => push({ tone: "error", message: `Approve failed: ${e.message}` }) },
              )
            }
          >
            approve
          </Button>
        )}
        <Button
          variant="ghost"
          disabled={!dirty || update.isPending}
          onClick={() =>
            update.mutate(
              { id: entry.id, payload: { answer } },
              { onError: (e) => push({ tone: "error", message: `Save failed: ${e.message}` }) },
            )
          }
        >
          save
        </Button>
        <Button
          variant="danger"
          disabled={remove.isPending}
          onClick={() =>
            remove.mutate(entry.id, {
              onError: (e) => push({ tone: "error", message: `Delete failed: ${e.message}` }),
            })
          }
        >
          delete
        </Button>
      </div>
    </div>
  )
}

export function AnswerBankManager() {
  const answersQuery = useAnswerBank()
  const create = useCreateAnswer()
  const { push } = useToast()

  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState("")

  function handleCreate() {
    if (!question.trim() || !answer.trim()) return
    create.mutate(
      { question: question.trim(), answer: answer.trim() },
      {
        onSuccess: () => {
          setQuestion("")
          setAnswer("")
        },
        onError: (error) => push({ tone: "error", message: `Could not add answer: ${error.message}` }),
      },
    )
  }

  const entries = answersQuery.data ?? []
  const pendingCount = entries.filter((e) => !e.approved).length

  return (
    <div className="flex flex-col gap-3">
      <p className="text-(--color-fg-dim) text-xs">
        Reusable answers to custom application questions. The agent fills approved answers with no LLM
        call; answers it generates appear here as <span className="text-(--color-accent)">suggested</span>{" "}
        until you approve them.
        {pendingCount > 0 && (
          <span className="text-(--color-accent)"> {pendingCount} pending review.</span>
        )}
      </p>

      <div className="flex flex-col gap-2 border-b border-(--color-border) pb-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">question</span>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Why do you want to work here?"
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-(--color-fg-dim)">answer</span>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={2}
            className="border border-(--color-border) bg-(--color-bg) px-1.5 py-1 text-(--color-fg)"
          />
        </label>
        <div>
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={create.isPending || !question.trim() || !answer.trim()}
          >
            add answer
          </Button>
        </div>
      </div>

      {answersQuery.isLoading ? (
        <p className="text-(--color-fg-dim) text-xs">loading…</p>
      ) : entries.length === 0 ? (
        <EmptyState
          title="No saved answers yet"
          hint="Add one above, or let the agent generate suggestions during an autofill run."
        />
      ) : (
        <div className="flex flex-col">
          {entries.map((entry) => (
            <AnswerRow key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
