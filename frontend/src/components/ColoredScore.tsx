import type React from 'react'
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ResultNote, Results } from '../lib/api'
import { alignMarks, type Box, measureBoxes, type NoteTip, paintScore, STATUS_COLOR, type ScoreMark, TIMING_COLOR } from '../lib/colorScore'
import type { NoteIdEntry } from '../lib/noteIds'
import { ScoreView } from './ScoreView'

// The score with every note colored from `results` (or plain while results is null). Colors are
// re-applied after every OSMD render (resize) and whenever `results` changes (e.g. re-graded in another
// mode), without reloading the score. `highlightBars` outlines those bars and scrolls to the first.
// The score scrolls inside `.score-page`; the legend sits under it, outside the scroll.
// `onPlayNote`: clicking a note that was sung (it has sung times) calls it, e.g. to play that stretch.
export function ColoredScore({
  xml,
  results,
  highlightBars = [],
  onPlayNote,
  children,
}: {
  xml: string
  results: Results | null
  highlightBars?: number[]
  onPlayNote?: (note: ResultNote) => void
  /** Drawn over the page (e.g. an "Analyzing…" dialog). */
  children?: ReactNode
}) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const entriesRef = useRef<NoteIdEntry[] | null>(null)
  const [marks, setMarks] = useState<ScoreMark[]>([])
  const [bars, setBars] = useState<Map<number, Box>>(new Map())
  const [tip, setTip] = useState<{ x: number; y: number; tail: number; below: boolean; tip: NoteTip } | null>(null)

  const paint = useCallback((r: Results | null) => {
    const entries = entriesRef.current
    if (!entries || !overlayRef.current) return
    setTip(null)
    setBars(measureBoxes(entries, overlayRef.current))
    if (!r) return setMarks([])
    const known = new Set(entries.map((e) => e.id))
    const missing = r.notes.filter((n) => !known.has(n.id)).map((n) => n.id)
    if (missing.length) console.warn('[color] result IDs with no note in this score:', missing)
    setMarks(alignMarks(paintScore(entries, r, overlayRef.current), overlayRef.current))
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

  // Scroll the page (only the page, never the desktop around it) to center the first highlighted bar.
  const pageRef = useRef<HTMLDivElement>(null)
  const firstBarRef = useRef<HTMLSpanElement>(null)
  const barsKey = highlightBars.join(',')
  useEffect(() => {
    const page = pageRef.current
    const bar = firstBarRef.current
    if (!barsKey || !page || !bar) return
    const p = page.getBoundingClientRect()
    const b = bar.getBoundingClientRect()
    page.scrollTo({ top: page.scrollTop + b.top - p.top - (page.clientHeight - b.height) / 2, behavior: 'smooth' })
  }, [barsKey])

  // The balloon sits above the note, or below it when it would run off the top of the visible page; it's
  // kept inside the page sideways, with its tail still pointing at the note.
  const showTip = (m: { x: number; y: number; w: number; h: number; tip: NoteTip }) => {
    const overlay = overlayRef.current
    const page = pageRef.current
    if (!overlay || !page) return
    const longest = Math.max(m.tip.title.length + 3, ...m.tip.lines.map((l) => l.length))
    const width = Math.max(150, longest * 7.3 + 26)
    const height = 30 + 17 * m.tip.lines.length
    const center = m.x + m.w / 2
    const x = Math.min(Math.max(center, width / 2 + 4), overlay.clientWidth - width / 2 - 4)
    const visibleTop = page.getBoundingClientRect().top - overlay.getBoundingClientRect().top
    const below = m.y - height - 16 < visibleTop
    setTip({ x, y: below ? m.y + m.h : m.y, tail: center - x, below, tip: m.tip })
  }
  // Notes that can be played: graded and actually sung (skipped notes have no sung times).
  const playable = useMemo(
    () => new Map((results?.notes ?? []).filter((n) => n.sung_start_sec !== null && n.sung_end_sec !== null).map((n) => [n.id, n])),
    [results],
  )
  const tipLabel = (t: NoteTip) => `${t.title}: ${t.lines.join(', ')}`
  const shown = highlightBars.filter((b) => bars.has(b))

  return (
    <>
      <div ref={pageRef} className="score-page well">
        {children}
        <ScoreView xml={xml} onRendered={onRendered}>
          <div ref={overlayRef} className="score-overlay">
            {shown.map((b, i) => {
              const box = bars.get(b)!
              return (
                <span
                  key={`bar-${b}`}
                  ref={i === 0 ? firstBarRef : undefined}
                  className="mark-bar"
                  // reaches up past the row of dots, so a dot never sits on the dashed edge
                  style={{ left: box.x, top: box.y - 16, width: box.w, height: box.h + 16 }}
                  aria-label={`Bar ${b}`}
                />
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
                      background: m.color,
                    }}
                  />
                )
              if (m.kind === 'hit') {
                const note = onPlayNote && m.noteId ? playable.get(m.noteId) : undefined
                return (
                  <span
                    key={i}
                    className={`mark-hit${note ? ' playable' : ''}`}
                    style={{ left: m.x, top: m.y, width: m.w, height: m.h }}
                    onMouseEnter={() => showTip(m)}
                    onMouseLeave={() => setTip(null)}
                    onClick={note && (() => onPlayNote?.(note))}
                  />
                )
              }
              // Dots are buttons, so the details are reachable from the keyboard too (Tab, then the balloon).
              const dot = { x: m.x - 4, y: m.y - 8, w: 8, h: 8, tip: m.tip }
              return (
                <button
                  key={i}
                  type="button"
                  className={`mark-dot${m.faded ? ' faded' : ''}`}
                  style={{ left: m.x, top: m.y, background: m.color }}
                  aria-label={tipLabel(m.tip)}
                  onMouseEnter={() => showTip(dot)}
                  onMouseLeave={() => setTip(null)}
                  onFocus={() => showTip(dot)}
                  onBlur={() => setTip(null)}
                />
              )
            })}
            {tip && (
              <div
                className={`score-tip${tip.below ? ' below' : ''}`}
                style={{ left: tip.x, top: tip.y, '--tail': `${tip.tail}px` } as React.CSSProperties}
                role="tooltip"
              >
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
      </div>
      {results && <Legend canPlay={!!onPlayNote} />}
    </>
  )
}

function Legend({ canPlay }: { canPlay: boolean }) {
  const swatches: [string, string][] = [
    ['In tune', STATUS_COLOR.in_tune],
    ['Out of tune', STATUS_COLOR.out_of_tune],
    ['Wrong note', STATUS_COLOR.wrong_note],
    ['Skipped', STATUS_COLOR.skipped],
  ]
  return (
    <div className="legend">
      {swatches.map(([label, color]) => (
        <span key={label}>
          <i className="swatch" style={{ background: `color-mix(in srgb, ${color} ${label === 'In tune' ? 16 : 30}%, white)` }} />
          {label}
        </span>
      ))}
      <span>
        <i className="legend-dot" style={{ background: TIMING_COLOR }} />
        Early / late
      </span>
      <span className="legend-hint">Point at a dot for details{canPlay ? ' · click a note to hear it' : ''}</span>
    </div>
  )
}
