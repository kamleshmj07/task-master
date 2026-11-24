import { type InputHTMLAttributes, useState } from 'react'

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  id: string
  /** What the field holds, for the eye button: "Show current password". */
  what?: string
}

/**
 * A password field with an eye button to see what was typed. Point a
 * `<label htmlFor>` at its `id`: a label wrapped around it would also read
 * out the button.
 */
export function PasswordInput({ id, what = 'password', ...input }: PasswordInputProps) {
  const [shown, setShown] = useState(false)
  return (
    <div className="password-field">
      <input
        {...input}
        id={id}
        type={shown ? 'text' : 'password'}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
      />
      <button
        type="button"
        className="password-toggle"
        aria-label={`${shown ? 'Hide' : 'Show'} ${what}`}
        aria-pressed={shown}
        aria-controls={id}
        onClick={() => setShown(!shown)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {shown ? (
            <path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A10 10 0 0 1 12 4c5 0 9 4 10 8a11 11 0 0 1-2.9 4.4M6.1 6.1A11 11 0 0 0 2 12c1 4 5 8 10 8a10 10 0 0 0 4.2-.9" />
          ) : (
            <path d="M2 12c1-4 5-8 10-8s9 4 10 8c-1 4-5 8-10 8S3 16 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
          )}
        </svg>
      </button>
    </div>
  )
}
