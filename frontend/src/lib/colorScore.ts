import type { ResultExtra, ResultNote, Results } from './api'
import type { NoteIdEntry } from './noteIds'
import type { GraphicalNote, VexFlowGraphicalNote, VexFlowMeasure } from 'opensheetmusicdisplay'

// GraphicalNotes are VexFlowGraphicalNotes at runtime (OSMD's SVG backend); that subclass has the SVG.
const svgOf = (gn: GraphicalNote | undefined) => (gn as VexFlowGraphicalNote | undefined)?.getSVGGElement?.()

// Works out the highlights and markers for results on the OSMD score (docs/DECISIONS.md section 6).
// Every graded note gets a soft highlight band: problems in their color, in-tune notes a very light green
// (`subtle`), so mistakes stand out. Timing problems and extras get their markers. Noteheads stay black.
//   in tune green · out of tune yellow · wrong note red · skipped grey (band only)
//   a dot above each problem note: red / yellow for pitch, else blue for early/late. Extra notes have no
//   mark: the balloon of the note they followed lists them. Dots sit on one baseline per line (alignMarks).
//   uncertain: its color, faded · hover: exact numbers.
// Positions come from the rendered SVG, so this runs again after every OSMD render.

export const STATUS_COLOR = {
  in_tune: '#1f9d55',
  out_of_tune: '#d49b00',
  wrong_note: '#d6334a',
  skipped: '#9a948c',
} as const

/** Timing marks (early / late). */
export const TIMING_COLOR = '#4b3fd1'
// The out-of-tune dot is a darker gold than its band, so a small dot stays visible on white.
const OUT_OF_TUNE_DOT = '#a87c00'

/** What the hover tooltip shows: the note's name, then one line per fact. */
export type NoteTip = { title: string; lines: string[]; color: string }

/** A marker in the overlay; x/y are pixels relative to the overlay's top-left. */
export type ScoreMark =
  // a dot above a note with a problem (pitch colour first, else timing); details in its balloon
  | { kind: 'dot'; x: number; y: number; color: string; faded: boolean; tip: NoteTip }
  | { kind: 'highlight'; x: number; y: number; w: number; h: number; color: string; faded: boolean; subtle: boolean }
  // invisible hover area over one notehead's column (bands join several notes; hover is per note)
  | { kind: 'hit'; x: number; y: number; w: number; h: number; tip: NoteTip; noteId?: string } // noteId: a graded note (clickable)

/** A box in overlay pixels. */
export type Box = { x: number; y: number; w: number; h: number }

/** Screen y (px) of the note's top and bottom staff lines, from its measure's VexFlow stave. */
function staffSpan(gn: GraphicalNote, group: SVGGElement): { top: number; bottom: number } | null {
  const measure = gn.parentVoiceEntry?.parentStaffEntry?.parentMeasure as VexFlowMeasure | undefined
  const stave = measure?.getVFStave?.()
  const ctm = group.ownerSVGElement?.getScreenCTM()
  if (!stave || !ctm) return null
  const y = (line: number) => new DOMPoint(0, stave.getYForLine(line)).matrixTransform(ctm).y
  return { top: y(0), bottom: y(4) }
}

function noteheads(group: SVGGElement): Element[] {
  const heads = [...group.querySelectorAll('.vf-notehead')]
  return heads.length ? heads : [group]
}

function centsText(cents: number): string {
  const n = Math.abs(Math.round(cents))
  return `${n} cent${n === 1 ? '' : 's'} ${cents < 0 ? 'flat' : 'sharp'}`
}

/** Tooltip for one note: "D5" / "Out of tune · 38 cents flat" / "140 ms late". */
export function noteTip(n: ResultNote): NoteTip {
  const lines: string[] = []
  if (n.status === 'skipped') lines.push('Skipped')
  else if (n.status === 'wrong_note') lines.push(`Wrong note · sang ${n.sang ?? '?'}`)
  else if (n.status === 'out_of_tune' && n.cents !== null) lines.push(`Out of tune · ${centsText(n.cents)}`)
  else lines.push(n.cents !== null && Math.abs(n.cents) >= 1 ? `In tune · ${centsText(n.cents)}` : 'In tune')
  if (n.timing === 'early' || n.timing === 'late') lines.push(`${Math.abs(n.timing_ms ?? 0)} ms ${n.timing}`)
  if (n.uncertain) lines.push('Hard to hear: not scored')
  return { title: n.lyric ? `${n.name} · “${n.lyric}”` : n.name, lines, color: STATUS_COLOR[n.status] }
}

export function paintScore(entries: NoteIdEntry[], results: Results, overlay: HTMLElement): ScoreMark[] {
  const origin = overlay.getBoundingClientRect()
  const rel = (r: DOMRect) => ({ x: r.left - origin.left, y: r.top - origin.top, w: r.width, h: r.height })
  const byId = new Map(results.notes.map((n) => [n.id, n]))
  const marks: ScoreMark[] = []

  // First drawn notehead (and its whole note group) for an ID, for positioning.
  const anchor = (entry: NoteIdEntry, renderId = entry.id) => {
    const group = svgOf(entry.graphical[renderId]?.[0])
    if (!group) return null
    const gn = entry.graphical[renderId]![0]
    const staff = staffSpan(gn, group)
    return {
      head: rel(noteheads(group)[0].getBoundingClientRect()),
      note: rel(group.getBoundingClientRect()),
      staff: staff && { top: staff.top - origin.top, bottom: staff.bottom - origin.top },
    }
  }

  // Highlight bands, in screen px: flat pastel boxes over the staff. Consecutive notes with the same verdict
  // on the same line of music join into one band (a run of wrong notes is one pink band, like a run of
  // in-tune notes is one green band); a rest, a different verdict or a line break ends it.
  type Band = { left: number; right: number; top: number; bottom: number; line: number; key: string; note: string; color: string; faded: boolean }
  const highlights: ScoreMark[] = []
  let run: Band | null = null
  const closeRun = () => {
    if (run) {
      highlights.push({
        kind: 'highlight',
        x: run.left - origin.left,
        y: run.top - origin.top,
        w: run.right - run.left,
        h: run.bottom - run.top,
        color: run.color,
        faded: run.faded,
        subtle: run.key.startsWith('in_tune'),
      })
    }
    run = null
  }

  // Extra notes have no mark of their own: they're listed in the balloon of the note (or rest) they came
  // after. Several near one ID are listed together.
  const extrasNear = new Map<string, ResultExtra[]>()
  for (const x of results.extras) extrasNear.set(x.near_id, [...(extrasNear.get(x.near_id) ?? []), x])
  const extraLines = (entry: NoteIdEntry) => {
    const xs = entry.render_ids.flatMap((rid) => extrasNear.get(rid) ?? [])
    if (!xs.length) return []
    const sang = xs.map((x) => x.sang).join(', ')
    return [`${xs.length === 1 ? 'An extra note' : `${xs.length} extra notes`} after: sang ${sang}`]
  }

  for (const entry of entries) {
    const r = entry.is_rest ? undefined : byId.get(entry.id)
    if (!r) closeRun() // rests break a run
    if (!r) {
      // A rest with extra notes sung during it: an invisible hover area over the rest shows them.
      const lines = extraLines(entry)
      const group = svgOf(entry.graphical[entry.id]?.[0])
      if (lines.length && group) {
        const box = rel(group.getBoundingClientRect())
        const during = entry.is_rest ? lines.map((l) => l.replace(' after', ' during this rest')) : lines
        marks.push({ kind: 'hit', x: box.x - 6, y: box.y - 10, w: box.w + 12, h: box.h + 20, tip: { title: 'Rest', lines: during, color: STATUS_COLOR.wrong_note } })
      }
      continue
    }
    const color = STATUS_COLOR[r.status]

    // A band behind every notehead of the note (all of them for ties), plus a hover area per notehead
    // that shows the numbers. In-tune notes get the same band, drawn very light (subtle).
    const base = noteTip(r)
    const tip = { ...base, lines: [...base.lines, ...extraLines(entry)] }
    const key = `${r.status}|${r.uncertain}`
    let bandTop = Infinity // top of this note's band, so labels sit above it
    for (const rid of entry.render_ids) {
      for (const gn of entry.graphical[rid] ?? []) {
        const group = svgOf(gn)
        if (!group) continue
        // A band over the notehead's column, from the top staff line to the bottom one (stretched to
        // reach notes on ledger lines). Falls back to the notehead alone if the staff can't be found.
        const staff = staffSpan(gn, group)
        for (const head of noteheads(group)) {
          const box = head.getBoundingClientRect()
          const padX = 7
          const padY = 12 // the band covers the staff plus a little above and below it
          // Same height on every note: the staff plus padY, growing only as far as a ledger-line notehead needs.
          const top = Math.min((staff?.top ?? box.top) - padY, box.top - 3)
          const bottom = Math.max((staff?.bottom ?? box.bottom) + padY, box.bottom + 3)
          bandTop = Math.min(bandTop, top - origin.top)
          const line = staff?.top ?? box.top // notes on the same line of music share their staff's top
          marks.push({ kind: 'hit', x: box.left - padX - origin.left, y: top - origin.top, w: box.width + 2 * padX, h: bottom - top, tip, noteId: r.id })
          const current = run as Band | null
          if (current && current.key === key && Math.abs(current.line - line) < 2) {
            current.left = Math.min(current.left, box.left - padX)
            current.right = Math.max(current.right, box.right + padX)
            current.top = Math.min(current.top, top)
            current.bottom = Math.max(current.bottom, bottom)
          } else {
            closeRun()
            run = { left: box.left - padX, right: box.right + padX, top, bottom, line, key, note: entry.id, color, faded: r.uncertain }
          }
        }
      }
    }

    const a = anchor(entry)
    if (!a) continue

    // One quiet dot per note with a problem: the band already says the pitch verdict, the balloon has
    // the details. Wrong / out of tune take the band's colour; otherwise early / late is blue. Skipped
    // notes get no dot (the grey band says it). alignMarks puts every dot of a line on one baseline.
    const timed = r.timing === 'early' || r.timing === 'late'
    const dotColor =
      r.status === 'wrong_note' || r.status === 'out_of_tune' ? color : r.status !== 'skipped' && timed ? TIMING_COLOR : null
    if (dotColor)
      marks.push({ kind: 'dot', x: a.head.x + a.head.w / 2, y: Math.min(a.note.y, a.head.y, bandTop) - 5, color: dotColor === STATUS_COLOR.out_of_tune ? OUT_OF_TUNE_DOT : dotColor, faded: r.uncertain, tip })
  }
  closeRun()

  return [...highlights, ...marks] // bands first, so the dots are drawn on top
}

/** Each bar's box (overlay pixels), from its staff as drawn: left to right edge, top to bottom staff line
 *  plus some room for notes above and below. Bars are numbered like the note IDs (m3-n0 is in bar 3). */
export function measureBoxes(entries: NoteIdEntry[], overlay: HTMLElement): Map<number, Box> {
  const origin = overlay.getBoundingClientRect()
  const boxes = new Map<number, Box>()
  for (const entry of entries) {
    const bar = Number(entry.id.slice(1, entry.id.indexOf('-')))
    if (boxes.has(bar)) continue
    const gn = entry.graphical[entry.id]?.[0]
    const group = svgOf(gn)
    const measure = gn?.parentVoiceEntry?.parentStaffEntry?.parentMeasure as VexFlowMeasure | undefined
    const stave = measure?.getVFStave?.()
    const ctm = group?.ownerSVGElement?.getScreenCTM()
    if (!stave || !ctm) continue
    const pt = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(ctm)
    const topLeft = pt(stave.getNoteStartX?.() ?? stave.getX(), stave.getYForLine(0))
    const bottomRight = pt(stave.getX() + stave.getWidth(), stave.getYForLine(4))
    const pad = 22
    boxes.set(bar, {
      x: topLeft.x - origin.left - 4,
      y: topLeft.y - origin.top - pad,
      w: bottomRight.x - topLeft.x + 8,
      h: bottomRight.y - topLeft.y + 2 * pad,
    })
  }
  return boxes
}

// ---------- mark layout: one baseline per line of music ----------

/**
 * Puts the dots of each line of music on one baseline (the highest resting position in
 * that line), raised above any of the score's own marks a dot would touch (tuplet numbers, bar numbers,
 * tempo marks, slurs, ties), so they read as a single tidy row above the staff. Mutates and returns `marks`.
 */
export function alignMarks(marks: ScoreMark[], overlay: HTMLElement): ScoreMark[] {
  const origin = overlay.getBoundingClientRect()
  const svg = overlay.parentElement?.querySelector('svg')
  // The score's own marks above the staff: words, numbers, tempo, tuplets, slurs and ties. Not lyrics, and
  // not the title block (ScoreView leaves room under it, so the first line's dots never jump over it).
  const texts = [
    ...(svg?.querySelectorAll(
      '.vf-text:not(.osmd-lyrics):not(.osmd-dash):not(.osmd-title):not(.osmd-subtitle):not(.osmd-composer):not(.osmd-lyricist), .vf-tuplet, .vf-stavetempo, .vf-curve, .vf-stavetie',
    ) ?? []),
  ]
    .map((t) => t.getBoundingClientRect())
    .filter((r) => r.width > 0)
    .map((r) => ({ x0: r.left - origin.left, x1: r.right - origin.left, y0: r.top - origin.top, y1: r.bottom - origin.top }))
  const MARK = 10 // a dot or + is about this tall and wide

  const row = marks.filter((m): m is Extract<ScoreMark, { kind: 'dot' }> => m.kind === 'dot')
  row.sort((a, b) => a.y - b.y)
  let line: typeof row = []
  const flush = () => {
    let base = Math.min(...line.map((m) => m.y))
    for (let tries = 0; tries < 4; tries++) {
      const hit = texts.filter((t) => line.some((m) => m.x - MARK / 2 < t.x1 + 2 && t.x0 - 2 < m.x + MARK / 2) && base - MARK < t.y1 + 2 && t.y0 < base)
      if (!hit.length) break
      base = Math.min(...hit.map((t) => t.y0)) - 3
    }
    for (const m of line) m.y = base
    line = []
  }
  for (const m of row) {
    if (line.length && m.y - line[0].y >= 60) flush() // lines of music are far further apart than 60px
    line.push(m)
  }
  if (line.length) flush()
  return marks
}
