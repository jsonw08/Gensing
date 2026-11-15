import { useCallback, useEffect, useRef, useState } from 'react'
import type { Results } from '../lib/api'
import { paintScore, STATUS_COLOR, type ScoreMark } from '../lib/colorScore'
import type { NoteIdEntry } from '../lib/noteIds'
import { ScoreView } from './ScoreView'

// The score with every note colored from `results` (or plain while results is null).
// Remount (key) when results change; colors are re-applied after every OSMD render.
export function ColoredScore({ xml, results }: { xml: string; results: Results | null }) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const resultsRef = useRef(results)
  useEffect(() => {
    resultsRef.current = results
  })
  const [marks, setMarks] = useState<ScoreMark[]>([])

  const onRendered = useCallback((_osmd: unknown, entries: NoteIdEntry[]) => {
    const r = resultsRef.current
    if (!r || !overlayRef.current) return
    const known = new Set(entries.map((e) => e.id))
    const missing = r.notes.filter((n) => !known.has(n.id)).map((n) => n.id)
    if (missing.length) console.warn('[color] result IDs with no note in this score:', missing)
    setMarks(paintScore(entries, r, overlayRef.current))
  }, [])

  return (
    <>
      {results && <Legend />}
      <ScoreView xml={xml} onRendered={onRendered}>
        <div ref={overlayRef} className="score-overlay">
          {marks.map((m, i) => {
            if (m.kind === 'highlight')
              return (
                <span
                  key={i}
                  className={`mark-highlight${m.faded ? ' faded' : ''}${m.subtle ? ' subtle' : ''}`}
                  title={m.title}
                  style={{
                    left: m.x,
                    top: m.y,
                    width: m.w,
                    height: m.h,
                    // soft glow: solid over the staff, fading out above and below it
                    background: `linear-gradient(to bottom, transparent, ${m.color} 30%, ${m.color} 70%, transparent)`,
                  }}
                />
              )
            if (m.kind === 'extra')
              return (
                <span key={i} className="mark-extra" title={m.title} style={{ left: m.x, top: m.y }}>
                  +{m.count > 1 ? m.count : ''}
                </span>
              )
            return (
              <span key={i} className="mark-label" style={{ left: m.x, top: m.y }}>
                {m.parts.map((p, j) => (
                  <span key={j} style={{ color: p.color }}>
                    {p.text}
                  </span>
                ))}
              </span>
            )
          })}
        </div>
      </ScoreView>
    </>
  )
}

function Legend() {
  const items: [string, string][] = [
    ['In tune', STATUS_COLOR.in_tune],
    ['Out of tune ↑↓', STATUS_COLOR.out_of_tune],
    ['Wrong note', STATUS_COLOR.wrong_note],
    ['Skipped ✕', STATUS_COLOR.skipped],
  ]
  return (
    <div className="legend">
      {items.map(([label, color]) => (
        <span key={label}>
          <i style={{ background: color, borderColor: color }} />
          {label}
        </span>
      ))}
      <span>
        <b style={{ color: STATUS_COLOR.wrong_note }}>+</b> Extra note
      </span>
      <span>
        <b style={{ color: '#4b3fd1' }}>early / late</b> Timing
      </span>
      <span className="legend-hint">Hover a note for details</span>
    </div>
  )
}
