// Decorative sheet-music backdrop (staves, barlines, notes). Purely visual; blurred via CSS.
const STAVES = 9
const STAFF_GAP = 112
const LINE_GAP = 10
const NOTE_STEP = 38
const LEFT = 60
const RIGHT = 770

// Deterministic pseudo-random melody so the backdrop looks the same on every render.
function melody(seed: number, count: number): number[] {
  const steps: number[] = []
  let pos = 4
  let s = seed
  for (let i = 0; i < count; i++) {
    s = (s * 9301 + 49297) % 233280
    pos += Math.floor((s / 233280) * 5) - 2
    pos = Math.max(-1, Math.min(9, pos))
    steps.push(pos)
  }
  return steps
}

export function BlurredSheet() {
  const notesPerStaff = Math.floor((RIGHT - LEFT - 40) / NOTE_STEP)

  return (
    <svg className="blurred-sheet" viewBox="0 0 800 1060" preserveAspectRatio="xMidYMin slice" aria-hidden="true">
      {Array.from({ length: STAVES }, (_, staff) => {
        const top = 70 + staff * STAFF_GAP
        const bottom = top + 4 * LINE_GAP
        const pitches = melody(staff + 7, notesPerStaff)
        return (
          <g key={staff}>
            {[0, 1, 2, 3, 4].map((l) => (
              <line key={l} x1={LEFT - 20} x2={RIGHT} y1={top + l * LINE_GAP} y2={top + l * LINE_GAP} />
            ))}
            <line x1={LEFT - 20} x2={LEFT - 20} y1={top} y2={bottom} />
            <line x1={RIGHT} x2={RIGHT} y1={top} y2={bottom} />
            {/* clef-ish swirl */}
            <path
              className="ink"
              d={`M ${LEFT - 2} ${bottom + 8} C ${LEFT - 12} ${top + 10}, ${LEFT + 12} ${top - 6}, ${LEFT + 2} ${top + 22} S ${LEFT - 10} ${bottom - 2}, ${LEFT + 4} ${bottom - 6}`}
              fill="none"
              strokeWidth={2.5}
            />
            {pitches.map((p, i) => {
              const x = LEFT + 40 + i * NOTE_STEP
              const y = bottom - p * (LINE_GAP / 2)
              const stemUp = p < 4
              const hollow = (i + staff) % 5 === 0
              return (
                <g key={i}>
                  {(i + 1) % 4 === 0 && i < pitches.length - 1 && (
                    <line x1={x + NOTE_STEP / 2} x2={x + NOTE_STEP / 2} y1={top} y2={bottom} />
                  )}
                  <ellipse
                    className="ink"
                    cx={x}
                    cy={y}
                    rx={6.5}
                    ry={4.6}
                    transform={`rotate(-20 ${x} ${y})`}
                    fill={hollow ? 'none' : undefined}
                    strokeWidth={hollow ? 1.8 : 0}
                  />
                  <line
                    className="stem"
                    x1={stemUp ? x + 6 : x - 6}
                    x2={stemUp ? x + 6 : x - 6}
                    y1={y}
                    y2={stemUp ? y - 32 : y + 32}
                  />
                </g>
              )
            })}
          </g>
        )
      })}
    </svg>
  )
}
