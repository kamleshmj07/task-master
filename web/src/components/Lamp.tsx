const RAYS = ['M120 108 112 128', 'M132 110 134 132', 'M143 104 156 120', 'M148 92 168 98']

/** The desk lamp of first-run setup: one ray per finished step, all four light it. */
export function Lamp({ lit, size = 180 }: { lit: number; size?: number }) {
  const on = lit >= RAYS.length
  const warm = lit > 0
  return (
    <svg width={size} height={size} viewBox="0 0 180 180" role="img" aria-label={`Lamp, ${lit} of ${RAYS.length} rays lit`}>
      {on && <ellipse cx="135" cy="160" rx="40" ry="7" fill="rgb(242 181 68 / 25%)" />}
      <path d="M40 160h70" stroke={on ? '#5a5240' : '#3a4357'} strokeWidth="8" strokeLinecap="round" fill="none" />
      <path
        d="M75 160 60 100l45-35"
        stroke={on ? '#5a5240' : '#3a4357'}
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M98 46l44 22-12 26-48-18Z"
        fill={on ? '#3a3322' : '#283042'}
        stroke={on ? '#f2b544' : warm ? '#a2803a' : '#3a4357'}
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <circle cx="122" cy="92" r={on ? 8 : 7} fill={on ? '#fff8ea' : warm ? '#c9963a' : '#3a4357'} />
      {RAYS.map((d, index) => (
        <path key={d} className={index < lit ? 'lamp-ray lit' : 'lamp-ray'} d={d} strokeWidth="5" strokeLinecap="round" />
      ))}
    </svg>
  )
}
