import { type ReactNode, useId } from 'react'

import { InfoTip } from '@/components/InfoTip'

interface FieldProps {
  label: string
  /** Extra explanation, shown behind an ⓘ button instead of under the field. */
  info?: ReactNode
  /** Renders the control; give it `id` so the label points at it. */
  children: (id: string) => ReactNode
}

/**
 * One form field: a label row (label, optional ⓘ) over its control. Every
 * field uses this shape, so fields line up wherever they sit in a grid.
 */
export function Field({ label, info, children }: FieldProps) {
  const id = useId()
  return (
    <div className="field">
      <div className="field-head">
        <label htmlFor={id}>{label}</label>
        {info && <InfoTip label={label}>{info}</InfoTip>}
      </div>
      {children(id)}
    </div>
  )
}

interface FieldGroupProps {
  label: string
  info?: ReactNode
  /** Several controls that together make one field; label each one. */
  children: ReactNode
}

/** A field made of several controls, such as an amount and a unit. */
export function FieldGroup({ label, info, children }: FieldGroupProps) {
  const id = useId()
  return (
    <div className="field" role="group" aria-labelledby={id}>
      <div className="field-head">
        <span id={id} className="field-label">
          {label}
        </span>
        {info && <InfoTip label={label}>{info}</InfoTip>}
      </div>
      {children}
    </div>
  )
}
