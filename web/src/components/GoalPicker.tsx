import type { GoalRead } from '@task-master/api-client'
import { useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field } from '@/components/Field'

const NEW_GOAL = '__new'

interface GoalPickerProps {
  goals: GoalRead[]
  /** The chosen goal's id, or '' for no goal. */
  value: string
  onChange: (goalId: string) => void
  /** Called after a goal is created here, e.g. to refresh other lists. */
  onGoalCreated?: (goal: GoalRead) => void
  info?: string
}

/** Choose a goal, or create one on the spot with "+ New goal…". */
export function GoalPicker({ goals, value, onChange, onGoalCreated, info }: GoalPickerProps) {
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  // Goals made here, so the list shows them before the parent reloads.
  const [created, setCreated] = useState<GoalRead[]>([])
  const [error, setError] = useState<string | null>(null)

  const options = [...goals, ...created.filter((goal) => !goals.some((g) => g.id === goal.id))]

  async function handleCreate() {
    const { data, error: apiError } = await api.POST('/goals', { body: { title: newTitle } })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setCreated([...created, data])
    setNewTitle('')
    setCreating(false)
    setError(null)
    onChange(data.id)
    onGoalCreated?.(data)
  }

  return (
    <div className="stack-sm">
      <Field label="Goal" info={info}>
        {(id) => (
          <select
            id={id}
            value={creating ? NEW_GOAL : value}
            onChange={(e) => {
              const next = e.target.value
              setCreating(next === NEW_GOAL)
              if (next !== NEW_GOAL) onChange(next)
            }}
          >
            <option value="">No goal</option>
            {options.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
            <option value={NEW_GOAL}>+ New goal…</option>
          </select>
        )}
      </Field>
      {creating && (
        <div className="row nowrap">
          <input
            className="grow"
            aria-label="New goal name"
            placeholder="New goal name"
            maxLength={200}
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              // Enter creates the goal instead of submitting the outer form.
              if (e.key === 'Enter') {
                e.preventDefault()
                if (newTitle.trim()) void handleCreate()
              }
            }}
          />
          <button type="button" disabled={!newTitle.trim()} onClick={() => void handleCreate()}>
            Create
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  )
}
