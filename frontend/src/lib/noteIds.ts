import type { GraphicalNote, OpenSheetMusicDisplay, VoiceEntry } from 'opensheetmusicdisplay'

// Note IDs (m{bar}-n{index}) built from OSMD's data, so the frontend can find the notehead for every ID
// the backend sends. TypeScript port of collectNoteIds() in tools/check_osmd_ids.mjs (on c/music-logic),
// which Mehul verified against stage 1 on 9 files. Rules: docs/DECISIONS.md section 3,
// "How the frontend counts (OSMD)". Change both sides together or not at all.

/** OSMD options the ID scheme depends on. Multi-rest off: otherwise several empty bars in a row are drawn
 *  as one symbol, those rests get no notehead, and an extra sung during them has nowhere to show. */
export const NOTE_ID_OSMD_OPTIONS = { autoGenerateMultipleRestMeasuresFromRestMeasures: false } as const

export type NoteIdEntry = {
  id: string
  is_rest: boolean
  midi: number | null
  onset_beats: number
  duration_beats: number
  /** This ID plus the IDs of tie continuations (one sung note, several noteheads). */
  render_ids: string[]
  /** Noteheads to color, per render ID. */
  graphical: Record<string, GraphicalNote[]>
}

/**
 * Build our note IDs from a loaded and rendered OSMD instance.
 * First part, voice 1; bars by position in the file from 1 (SourceMeasures index, NOT MeasureNumber,
 * which is the printed number: pickups print as 0); index from 0 in time order; rests count;
 * grace notes skipped; chord = one index (top note); a tie continuation takes an index but no entry:
 * its ID goes into the first notehead's render_ids.
 */
export function collectNoteIds(osmd: OpenSheetMusicDisplay): NoteIdEntry[] {
  const rules = osmd.EngravingRules
  const entries: NoteIdEntry[] = []
  osmd.Sheet.SourceMeasures.forEach((measure, i) => {
    const bar = i + 1
    // Voice entries on the first staff of the first instrument (= music21's first part), grace skipped
    const onStaff: { ve: VoiceEntry; onset: number }[] = []
    for (const container of measure.VerticalSourceStaffEntryContainers) {
      const staffEntry = container.StaffEntries[0]
      if (!staffEntry) continue
      for (const ve of staffEntry.VoiceEntries) {
        if (!ve.IsGrace) onStaff.push({ ve, onset: measure.AbsoluteTimestamp.RealValue + container.Timestamp.RealValue })
      }
    }
    const voiceIds = [...new Set(onStaff.map((x) => x.ve.ParentVoice.VoiceId))]
    const voiceOne = voiceIds.includes(1) ? 1 : voiceIds[0] // "voice 1", else the first voice in the bar
    let index = 0
    for (const { ve, onset } of onStaff.filter((x) => x.ve.ParentVoice.VoiceId === voiceOne)) {
      const id = `m${bar}-n${index++}`
      const notes = ve.Notes
      const isRest = notes[0].isRest()
      const top = isRest ? null : notes.reduce((a, b) => (b.Pitch.getHalfTone() > a.Pitch.getHalfTone() ? b : a))
      const graphical = notes.map((n) => rules.GNote(n)).filter(Boolean)
      const prev = entries[entries.length - 1]
      const tieContinuation = !!top && !!top.NoteTie && top.NoteTie.StartNote !== top
      if (tieContinuation && prev && !prev.is_rest) {
        prev.render_ids.push(id)
        prev.duration_beats += notes[0].Length.RealValue * 4
        prev.graphical[id] = graphical
        continue
      }
      entries.push({
        id,
        is_rest: isRest,
        midi: top ? top.Pitch.getHalfTone() + 12 : null, // OSMD half tones: C4 = 48
        onset_beats: onset * 4, // OSMD timestamps are in whole notes; ours are quarter beats
        duration_beats: notes[0].Length.RealValue * 4,
        render_ids: [id],
        graphical: { [id]: graphical },
      })
    }
  })
  return entries
}

/** Map from every render ID (including tie continuations) to the noteheads to color. */
export function noteheadsById(entries: NoteIdEntry[]): Map<string, GraphicalNote[]> {
  const map = new Map<string, GraphicalNote[]>()
  for (const e of entries) for (const rid of e.render_ids) map.set(rid, e.graphical[rid])
  return map
}
