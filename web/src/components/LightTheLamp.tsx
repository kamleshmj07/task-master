import type { OnboardingRead } from '@task-master/api-client'
import { type FormEvent, type ReactNode, useState } from 'react'

import { api, errorMessage } from '@/api'
import { Lamp } from '@/components/Lamp'
import { addDays, todayIso } from '@/dates'
import { GOAL_IDEAS, ROUTINE_IDEAS, setupSteps } from '@/onboarding'

interface LightTheLampProps {
  state: OnboardingRead
  name: string | null | undefined
  /** Something was created; reload what the card and the page show. */
  onChanged: () => void
  onAddToThree: (taskId: string) => void
  onFinish: () => void
  onReadTips: () => void
  onHide: () => void
}

/**
 * First-run setup on Today: four steps, done right here. Each finished step
 * lights one ray of the lamp; with all four lit, it welcomes the user.
 */
export function LightTheLamp({ state, name, onChanged, onAddToThree, onFinish, onReadTips, onHide }: LightTheLampProps) {
  const steps = setupSteps(state)
  const lit = steps.filter(Boolean).length
  const current = steps.findIndex((done) => !done)

  if (current === -1) {
    return (
      <section className="lamp-card lit" aria-labelledby="lamp-heading">
        <div className="lamp-art glow">
          <Lamp lit={4} size={200} />
          <span className="lamp-count on">4 of 4 lit</span>
        </div>
        <div className="lamp-body">
          <div className="stack-sm">
            <h2 id="lamp-heading">{name ? `Your lamp is on, ${name}` : 'Your lamp is on'}</h2>
            <p className="lamp-lede">Your desk is set up. From here on, every day works the same simple way.</p>
          </div>
          <ul className="lamp-how">
            <How title="Each morning, pick your three" icon="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M19 12h2M17 7l1.4-1.4M8 16a4 4 0 1 1 8 0M4 20h16">
              What's left from yesterday is waiting for you at the top.
            </How>
            <How title="Work on the lit step" icon="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 3Z">
              One step at a time. The light moves on as you tick them off.
            </How>
            <How title="Putting something off? Say why" icon="M12 8v4l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z">
              Postpone honestly and you'll get a tip that fits the reason.
            </How>
          </ul>
          <div className="row">
            <button type="button" className="primary lamp-start" onClick={onFinish}>
              Start my day
            </button>
            <button type="button" onClick={onReadTips}>
              Read the tips
            </button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="lamp-card" aria-labelledby="lamp-heading">
      <div className="lamp-art">
        <Lamp lit={lit} />
        <span className={lit > 0 ? 'lamp-count on' : 'lamp-count'}>{lit} of 4 lit</span>
        <span className="small muted">{lit === 0 ? 'About two minutes' : lit === 2 ? 'Halfway there' : 'Keep going'}</span>
      </div>
      <div className="lamp-body">
        <div className="row between top">
          <div className="stack-sm">
            <h2 id="lamp-heading">Light your lamp</h2>
            <p className="lamp-lede">
              {lit === 0 ? 'Four small steps to set up your desk. Each one you finish lights a ray.' : `Nice. ${lit === 1 ? 'One ray' : lit === 2 ? 'Two rays' : 'Three rays'} on.`}
            </p>
          </div>
          <button type="button" className="ghost" onClick={onHide}>
            Not now
          </button>
        </div>
        <ol className="lamp-steps">
          <Step number={1} done={steps[0] ?? false} current={current === 0} title="Name something you're working toward" doneTitle="Goal set" summary={state.goal?.title}>
            <p className="muted">A goal gives your tasks a reason. Big or small, you can change it any time.</p>
            <GoalStep onCreated={onChanged} />
          </Step>
          <Step
            number={2}
            done={steps[1] ?? false}
            current={current === 1}
            title="Add a task, with a first step so small it's hard to say no"
            hint="“Look up three shoe shops” beats “Get fit”."
            doneTitle="First task added"
            summary={state.task ? `${state.task.title}. First step: ${state.task.first_step ?? ''}` : undefined}
            cheer="A first step that small is the hardest part done."
          >
            <TaskStep goalId={state.goal?.id ?? null} onCreated={onChanged} />
          </Step>
          <Step
            number={3}
            done={steps[2] ?? false}
            current={current === 2}
            title="Pick your three for today"
            hint="The first one gets the light. That's where you start."
            doneTitle="Your three are picked"
          >
            <p className="muted">Even one is enough to start. The first one you pick gets the light.</p>
            {state.task && (
              <div className="lamp-pick">
                <div className="grow">
                  <p className="strong">{state.task.title}</p>
                  <p className="small muted">{state.goal ? `Your new task, for ${state.goal.title}` : 'Your new task'}</p>
                </div>
                <button
                  type="button"
                  className="primary"
                  aria-label={`Add “${state.task.title}” to your three`}
                  onClick={() => state.task && onAddToThree(state.task.id)}
                >
                  Add
                </button>
              </div>
            )}
          </Step>
          <Step
            number={4}
            done={steps[3] ?? false}
            current={current === 3}
            title="Add one routine"
            hint="A walk, vitamins, ten minutes of reading. Every tick grows a streak."
            doneTitle="Routine added"
            summary={state.routine?.title}
          >
            <p className="muted">Something small you do every day. Tick it off on Today to grow a streak.</p>
            <RoutineStep onCreated={onChanged} />
          </Step>
        </ol>
      </div>
    </section>
  )
}

interface StepProps {
  number: number
  done: boolean
  current: boolean
  title: string
  hint?: string
  doneTitle: string
  summary?: string | undefined
  cheer?: string
  children: ReactNode
}

function Step({ number, done, current, title, hint, doneTitle, summary, cheer, children }: StepProps) {
  if (done) {
    return (
      <li className="lamp-step done">
        <span className="lamp-node done" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </span>
        <div className="grow">
          <h3 className="lamp-step-done">
            <span className="visually-hidden">Step {number} done: </span>
            {doneTitle}
          </h3>
          {summary && <p>{summary}</p>}
          {cheer && <p className="small gain">{cheer}</p>}
        </div>
      </li>
    )
  }
  return (
    <li className={current ? 'lamp-step current' : 'lamp-step'} aria-current={current ? 'step' : undefined}>
      <span className={current ? 'lamp-node lit' : 'lamp-node'} aria-hidden="true">
        {number}
      </span>
      <div className="grow stack-sm">
        <h3 className={current ? 'lamp-step-title current' : 'lamp-step-title'}>
          <span className="visually-hidden">Step {number}: </span>
          {title}
        </h3>
        {!current && hint && <p className="small muted">{hint}</p>}
        {current && children}
      </div>
    </li>
  )
}

function How({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <li>
      <span className="lamp-how-icon" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d={icon} />
        </svg>
      </span>
      <div>
        <p className="strong">{title}</p>
        <p className="muted">{children}</p>
      </div>
    </li>
  )
}

/** A text field with idea chips that fill it, and a submit button. */
function QuickForm({
  label,
  ideas,
  submitLabel,
  onSubmit,
}: {
  label: string
  ideas: readonly string[]
  submitLabel: string
  onSubmit: (value: string) => Promise<string | null>
}) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    const failure = await onSubmit(value.trim())
    setBusy(false)
    setError(failure)
  }

  return (
    <form className="stack-sm" onSubmit={handleSubmit}>
      <div className="row lamp-quick">
        <label className="grow">
          {label}
          <input required maxLength={200} value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
        <button type="submit" className="primary" disabled={busy || !value.trim()}>
          {submitLabel}
        </button>
      </div>
      <div className="chips" role="group" aria-label="Ideas">
        <span className="small muted">Ideas:</span>
        {ideas.map((idea) => (
          <button key={idea} type="button" className="chip" aria-pressed={value === idea} onClick={() => setValue(idea)}>
            {idea}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  )
}

function GoalStep({ onCreated }: { onCreated: () => void }) {
  return (
    <QuickForm
      label="Your goal"
      ideas={GOAL_IDEAS}
      submitLabel="Set goal"
      onSubmit={async (title) => {
        const { error } = await api.POST('/goals', { body: { title } })
        if (error) return errorMessage(error)
        onCreated()
        return null
      }}
    />
  )
}

function TaskStep({ goalId, onCreated }: { goalId: string | null; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [firstStep, setFirstStep] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const { error: apiError } = await api.POST('/tasks', {
      body: { title, steps: [firstStep], goal_id: goalId },
    })
    if (apiError) {
      setError(errorMessage(apiError))
      return
    }
    onCreated()
  }

  return (
    <form className="stack-sm" onSubmit={handleSubmit}>
      <div className="grid">
        <label>
          Task
          <input required maxLength={200} placeholder="Buy running shoes" value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Its first step
          <input required maxLength={500} placeholder="Look up three shoe shops" value={firstStep} onChange={(e) => setFirstStep(e.target.value)} />
        </label>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div>
        <button type="submit" className="primary" disabled={!title.trim() || !firstStep.trim()}>
          Add task
        </button>
      </div>
    </form>
  )
}

function RoutineStep({ onCreated }: { onCreated: () => void }) {
  return (
    <QuickForm
      label="Your routine"
      ideas={ROUTINE_IDEAS}
      submitLabel="Add routine"
      onSubmit={async (title) => {
        const today = todayIso()
        const { error } = await api.POST('/routines', {
          // Daily for a year; it can be changed on the Routines page.
          body: { title, frequency: 'daily', start_date: today, end_date: addDays(today, 365) },
        })
        if (error) return errorMessage(error)
        onCreated()
        return null
      }}
    />
  )
}
