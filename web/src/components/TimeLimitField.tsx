import { MAX_MINUTES, type TimeUnit } from '@/data'

interface TimeLimitFieldProps {
  amount: string
  unit: TimeUnit
  onAmountChange: (amount: string) => void
  onUnitChange: (unit: TimeUnit) => void
}

/** Optional total time for a task: an amount plus minutes or hours. */
export function TimeLimitField({ amount, unit, onAmountChange, onUnitChange }: TimeLimitFieldProps) {
  const hours = unit === 'hours'
  return (
    <fieldset className="plain stack-sm">
      <legend>
        Time limit <span className="muted">· optional, total time</span>
      </legend>
      <div className="row nowrap">
        <input
          className="grow"
          type="number"
          inputMode="decimal"
          aria-label="Time limit amount"
          placeholder="No limit"
          min={hours ? 0.25 : 1}
          max={hours ? MAX_MINUTES / 60 : MAX_MINUTES}
          step={hours ? 0.25 : 1}
          value={amount}
          onChange={(e) => onAmountChange(e.target.value)}
        />
        <select aria-label="Time limit unit" value={unit} onChange={(e) => onUnitChange(e.target.value as TimeUnit)}>
          <option value="min">minutes</option>
          <option value="hours">hours</option>
        </select>
      </div>
    </fieldset>
  )
}
