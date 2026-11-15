import { useCallback, useEffect, useRef, useState } from 'react'
import type { Results } from '../lib/api'
import { type Box, measureBoxes, type NoteTip, paintScore, STATUS_COLOR, type ScoreMark } from '../lib/colorScore'
import type { NoteIdEntry } from '../lib/noteIds'
import { ScoreView } from './ScoreView'

// The score with every note colored from `results` (or plain while results is null). Colors are
// re-applied after every OSMD render (resize) and whenever `results` changes (e.g. re-graded in another
// mode), without reloading the score. `highlightBars` outlines those bars and scrolls to the first.
export function ColoredScore({
  xml,
  results,
  highlightBars = [],
}: {
  xml: string
  results: Results | null
  highlightBars?: number[]
}) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const entriesRef = useRef<NoteIdEntry[] | null>(null)
  const [marks, setMarks] = useState<ScoreMark[]>([])
  const [bars, setBars] = useState<Map<number, Box>>(new Map())
  const [tip, setTip] = useState<{ x: number; y: number; tip: NoteTip } | null>(null)

  const paint = useCallback((r: Results | null) => {
    const entries = entriesRef.current
    if (!entries || !overlayRef.current) return
    setTip(null)
    setBars(measureBoxes(entries, overlayRef.current))
    if (!r) return setMarks([])
    const known = new Set(entries.map((e) => e.id))
    const missing = r.notes.filter((n) => !known.has(n.id)).map((n) => n.id)
    if (missing.length) console.warn('[color] result IDs with no note in this score:', missing)
    setMarks(paintScore(entries, r, overlayRef.current))
  }, [])

  const resultsRef = useRef(results)
  useEffect(() => {
    resultsRef.current = results
    paint(results)
  }, [results, paint])

  const onRendered = useCallback(
    (_osmd: unknown, entries: NoteIdEntry[]) => {
      entriesRef.current = entries
      paint(resultsRef.current)
    },
    [paint],
  )

  // Scroll the first highlighted bar into view when the highlight changes.
  const firstBarRef = useRef<HTMLSpanElement>(null)
  const barsKey = highlightBars.join(',')
  useEffect(() => {
    if (barsKey) firstBarRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [barsKey])

  const showTip = (m: { x: number; y: number; w: number; tip: NoteTip }) => setTip({ x: m.x + m.w / 2, y: m.y, tip: m.tip })
  const shown = highlightBars.filter((b) => bars.has(b))

  return (
    <>
      {results && <Legend />}
      <ScoreView xml={xml} onRendered={onRendered}>
        <div ref={overlayRef} className="score-overlay">
          {shown.map((b, i) => {
            const box = bars.get(b)!
            return (
              <span
                key={`bar-${b}`}
                ref={i === 0 ? firstBarRef : undefined}
                className="mark-bar"
                style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
              >
                <span>Bar {b}</span>
              </span>
            )
          })}
          {marks.map((m, i) => {
            if (m.kind === 'highlight')
              return (
                <span
                  key={i}
                  className={`mark-highlight${m.faded ? ' faded' : ''}${m.subtle ? ' subtle' : ''}`}
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
            if (m.kind === 'hit')
              return (
                <span
                  key={i}
                  className="mark-hit"
                  style={{ left: m.x, top: m.y, width: m.w, height: m.h }}
                  onMouseEnter={() => showTip(m)}
                  onMouseLeave={() => setTip(null)}
                />
              )
            if (m.kind === 'extra')
              return (
                <span
                  key={i}
                  className="mark-extra"
                  style={{ left: m.x, top: m.y }}
                  onMouseEnter={() => showTip({ x: m.x, y: m.y - 10, w: 10, tip: m.tip })}
                  onMouseLeave={() => setTip(null)}
                >
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
          {tip && (
            <div className="score-tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
              <strong>
                <i style={{ background: tip.tip.color }} />
                {tip.tip.title}
              </strong>
              {tip.tip.lines.map((line, i) => (
                <span key={i}>{line}</span>
              ))}
            </div>
          )}
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
