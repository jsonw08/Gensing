// Tempo and time signature from MusicXML, for the count-in. Tempo is always in quarter notes per
// minute (our beat unit, docs/DECISIONS.md). Only the first marking counts: no tempo changes yet.

export const DEFAULT_TEMPO_BPM = 80

export type ScoreTiming = {
  tempoBpm: number // quarter notes per minute
  beats: number // time signature top, e.g. 3 in 3/4
  beatType: number // time signature bottom, e.g. 4 in 3/4
}

const UNIT_IN_QUARTERS: Record<string, number> = { whole: 4, half: 2, quarter: 1, eighth: 0.5, '16th': 0.25 }

export function readScoreTiming(xml: string): ScoreTiming {
  const doc = new DOMParser().parseFromString(xml, 'application/xml')

  // <sound tempo> is defined in quarter notes per minute; otherwise convert the <metronome> mark.
  let tempo = Number(doc.querySelector('sound[tempo]')?.getAttribute('tempo'))
  if (!(tempo > 0)) {
    const metronome = doc.querySelector('metronome')
    const perMinute = Number(metronome?.querySelector('per-minute')?.textContent)
    const unit = UNIT_IN_QUARTERS[metronome?.querySelector('beat-unit')?.textContent?.trim() ?? ''] ?? 1
    const dotted = metronome?.querySelector('beat-unit-dot') ? 1.5 : 1
    tempo = perMinute * unit * dotted
  }

  const time = doc.querySelector('time')
  const beats = Number(time?.querySelector('beats')?.textContent)
  const beatType = Number(time?.querySelector('beat-type')?.textContent)

  return {
    tempoBpm: tempo > 0 ? Math.round(tempo) : DEFAULT_TEMPO_BPM,
    beats: beats > 0 ? beats : 4,
    beatType: beatType > 0 ? beatType : 4,
  }
}

/** One bar of clicks: one per time-signature beat (3 in 3/4, 6 in 6/8), spaced by the tempo. */
export function countInFor(timing: Pick<ScoreTiming, 'beats' | 'beatType'>, tempoBpm: number) {
  const quarterSec = 60 / tempoBpm
  return { beats: timing.beats, intervalSec: quarterSec * (4 / timing.beatType) }
}

/** The piece's title from MusicXML (work title, else movement title), or null. */
export function readScoreTitle(xml: string): string | null {
  const doc = new DOMParser().parseFromString(xml, 'application/xml')
  const title = doc.querySelector('work > work-title')?.textContent?.trim() || doc.querySelector('movement-title')?.textContent?.trim()
  return title || null
}
