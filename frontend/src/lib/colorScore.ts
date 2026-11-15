import type { ResultExtra, ResultNote, Results } from './api'
import type { NoteIdEntry } from './noteIds'
import type { GraphicalNote, VexFlowGraphicalNote, VexFlowMeasure } from 'opensheetmusicdisplay'

// GraphicalNotes are VexFlowGraphicalNotes at runtime (OSMD's SVG backend); that subclass has the SVG.
const svgOf = (gn: GraphicalNote | undefined) => (gn as VexFlowGraphicalNote | undefined)?.getSVGGElement?.()

// Works out the highlights and markers for results on the OSMD score (docs/DECISIONS.md section 6).
// Every graded note gets a soft highlight band: problems in their color, in-tune notes a very light green
// (`subtle`), so mistakes stand out. Timing problems and extras get their markers. Noteheads stay black.
//   in tune green · out of tune yellow + ↑/↓ · wrong note red + "sang X" · skipped grey + ✕
//   early/late small marker above (notehead color stays with pitch) · extra red + next to near_id
//   uncertain: its color, faded · hover: exact numbers.
// Positions come from the rendered SVG, so this runs again after every OSMD render.

export const STATUS_COLOR = {
  in_tune: '#1f9d55',
  out_of_tune: '#d49b00',
  wrong_note: '#d6334a',
  skipped: '#9a948c',
} as const

/** What the hover tooltip shows: the note's name, then one line per fact. */
export type NoteTip = { title: string; lines: string[]; color: string }

/** A marker in the overlay; x/y are pixels relative to the overlay's top-left. */
export type ScoreMark =
  | { kind: 'label'; x: number; y: number; parts: { text: string; color: string }[] }
  | { kind: 'extra'; x: number; y: number; count: number; tip: NoteTip }
  | { kind: 'highlight'; x: number; y: number; w: number; h: number; color: string; faded: boolean; subtle: boolean }
  // invisible hover area over one notehead's column (bands join several notes; hover is per note)
  | { kind: 'hit'; x: number; y: number; w: number; h: number; tip: NoteTip }

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
    return { head: rel(noteheads(group)[0].getBoundingClientRect()), note: rel(group.getBoundingClientRect()) }
  }

  // Highlight bands, in screen px. Consecutive notes with the same problem on the same line of music
  // are joined into one band; a rest, an in-tune note, a different problem or a line break ends it.
  type Band = { left: number; right: number; top: number; bottom: number; line: number; key: string; color: string; faded: boolean }
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

  for (const entry of entries) {
    const r = entry.is_rest ? undefined : byId.get(entry.id)
    if (!r) closeRun() // rests break a run
    if (!r) continue
    const color = STATUS_COLOR[r.status]

    // A band behind every notehead of the note (all of them for ties), plus a hover area per notehead
    // that shows the numbers. In-tune notes get the same band, drawn very light (subtle).
    const tip = noteTip(r)
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
          const padX = 3
          const padY = 18 // the soft glow fades out over this distance above and below the staff
          const top = Math.min(staff?.top ?? box.top, box.top) - padY
          const bottom = Math.max(staff?.bottom ?? box.bottom, box.bottom) + padY
          bandTop = Math.min(bandTop, top - origin.top)
          const line = staff?.top ?? box.top // notes on the same line of music share their staff's top
          marks.push({ kind: 'hit', x: box.left - padX - origin.left, y: top - origin.top, w: box.width + 2 * padX, h: bottom - top, tip })
          const current = run as Band | null
          if (current && current.key === key && Math.abs(current.line - line) < 2) {
            current.left = Math.min(current.left, box.left - padX)
            current.right = Math.max(current.right, box.right + padX)
            current.top = Math.min(current.top, top)
            current.bottom = Math.max(current.bottom, bottom)
          } else {
            closeRun()
            run = { left: box.left - padX, right: box.right + padX, top, bottom, line, key, color, faded: r.uncertain }
          }
        }
      }
    }

    const a = anchor(entry)
    if (!a) continue

    const parts: { text: string; color: string }[] = []
    if (r.status === 'out_of_tune' && r.cents !== null) parts.push({ text: r.cents < 0 ? '↓' : '↑', color })
    if (r.status === 'wrong_note') parts.push({ text: `sang ${r.sang ?? '?'}`, color })
    if (r.status === 'skipped') parts.push({ text: '✕', color })
    if (r.timing === 'early' || r.timing === 'late') parts.push({ text: r.timing, color: '#4b3fd1' })
    if (parts.length) marks.push({ kind: 'label', x: a.head.x + a.head.w / 2, y: Math.min(a.note.y, a.head.y, bandTop) - 3, parts })
  }
  closeRun()

  // Extras: a red + to the right of near_id (a note or a rest). Several near one ID are counted.
  const extrasNear = new Map<string, ResultExtra[]>()
  for (const x of results.extras) extrasNear.set(x.near_id, [...(extrasNear.get(x.near_id) ?? []), x])
  const entryByRenderId = new Map(entries.flatMap((e) => e.render_ids.map((rid) => [rid, e] as const)))
  for (const [nearId, extras] of extrasNear) {
    const entry = entryByRenderId.get(nearId)
    const a = entry && anchor(entry, nearId)
    if (!a) continue
    marks.push({
      kind: 'extra',
      x: a.head.x + a.head.w + 3,
      y: a.head.y + a.head.h / 2,
      count: extras.length,
      tip: {
        title: extras.length === 1 ? 'Extra note' : `${extras.length} extra notes`,
        lines: extras.map((x) => `Sang ${x.sang}${x.during_rest ? ' during a rest' : ''}`),
        color: STATUS_COLOR.wrong_note,
      },
    })
  }
  return [...highlights, ...marks] // bands first, so labels and + are drawn on top
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
