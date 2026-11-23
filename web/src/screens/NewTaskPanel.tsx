import type { GoalRead } from '@task-master/api-client'
import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Field, FieldGroup } from '@/components/Field'
import { CloseIcon } from '@/components/Modal'
import { TimeLimitField } from '@/components/TimeLimitField'
import { type TimeUnit, toMinutes } from '@/data'

const NEW_GOAL = '__new'

interface NewTaskPanelProps {
  goals: GoalRead[]
  onGoalCreated: () => void
  onCreated: (title: string, someday: boolean) => void
  onClose: () => void
}

/** Capture a task: title, ordered steps (first required), goal, limit, date. */
export function NewTaskPanel({ goals, onGoalCreated, onCreated, onClose }: NewTaskPanelProps) {
  const [title, setTitle] = useState('')
  const [steps, setSteps] = useState([''])
  const [goalId, setGoalId] = useState('')
  const [newGoal, setNewGoal] = useState('')
  const [limitAmount, setLimitAmount] = useState('')
  const [limitUnit, setLimitUnit] = useState<TimeUnit>('min')
  const [dueDate, setDueDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  const creatingGoal = goalId === NEW_GOAL

  async function handleCreateGoal() {
    const { data, error: apiError } = await api.POST('/goals', { body: { title: newGoal } })
    if (apiError || !data) {
      setError(errorMessage(apiError))
      return
    }
    setNewGoal('')
    setGoalId(data.id)
    setError(null)
    onGoalCreated()
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.POST('/tasks', {
      body: {
        title,
        steps: steps.map((step) => step.trim()).filter(Boolean),
        goal_id: goalId && !creatingGoal ? goalId : null,
        time_limit_minutes: toMinutes(limitAmount, limitUnit),
        due_date: dueDate || null,
      },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    onCreated(title.trim(), !dueDate)
  }

  return (
    <form className="card stack" aria-label="New task" onSubmit={handleSubmit}>
      <div className="row between">
        <h2>New task</h2>
        <button type="button" className="ghost icon" aria-label="Close new task" onClick={onClose}>
          <CloseIcon />
        </button>
      </div>

      <Field label="Task">
        {(id) => (
          <input
            id={id}
            required
            maxLength={200}
            placeholder="e.g. Renew car insurance"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        )}
      </Field>

      <FieldGroup
        label="Steps"
        info="Start with the very first physical action, small enough to begin right away. The first unfinished step is always shown as the task's next step. You can add, reorder and tick steps later."
      >
        {steps.map((step, index) => (
          <div key={index} className="row nowrap">
            <span className="step-number" aria-hidden="true">
              {index + 1}
            </span>
            <input
              className="grow"
              aria-label={`Step ${index + 1}`}
              placeholder={index === 0 ? 'First step, e.g. Find the policy number' : 'Another step'}
              required={index === 0}
              maxLength={500}
              value={step}
              onChange={(e) => setSteps(steps.map((s, i) => (i === index ? e.target.value : s)))}
            />
            {index > 0 && (
              <button
                type="button"
                className="ghost icon"
                aria-label={`Remove step ${index + 1}`}
                onClick={() => setSteps(steps.filter((_, i) => i !== index))}
              >
                <CloseIcon />
              </button>
            )}
          </div>
        ))}
        <div>
          <button type="button" className="ghost accent" onClick={() => setSteps([...steps, ''])}>
            + Add step
          </button>
        </div>
      </FieldGroup>

      <div className="grid">
        <div className="stack-sm">
          <Field label="Goal" info="The outcome this task moves you toward. Optional: everyday chores can stay goal-less or go under Essentials.">
            {(id) => (
              <select id={id} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
                <option value="">No goal</option>
                {goals.map((goal) => (
                  <option key={goal.id} value={goal.id}>
                    {goal.title}
                  </option>
                ))}
                <option value={NEW_GOAL}>+ New goal…</option>
              </select>
            )}
          </Field>
          {creatingGoal && (
            <div className="row nowrap">
              <input
                className="grow"
                aria-label="New goal name"
                placeholder="New goal name"
                maxLength={200}
                value={newGoal}
                onChange={(e) => setNewGoal(e.target.value)}
              />
              <button type="button" disabled={!newGoal.trim()} onClick={() => void handleCreateGoal()}>
                Create
              </button>
            </div>
          )}
        </div>
        <TimeLimitField
          amount={limitAmount}
          unit={limitUnit}
          onAmountChange={setLimitAmount}
          onUnitChange={setLimitUnit}
        />
        <Field label="Due date" info="Leave it empty to keep the task in Someday. Moving a date later is a postponement, so it asks why.">
          {(id) => <input id={id} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />}
        </Field>
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="primary">
          Add task
        </button>
        <button type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}
