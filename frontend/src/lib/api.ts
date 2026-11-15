// Thin client for the backend. Shapes follow /contracts (to be locked in step 2).

export type AnalyzeSettings = {
  mode: 'strict' | 'free'
  tempoBpm?: number
  preset?: 'default' | 'beginner' | 'advanced'
  countinEndSec?: number
}

export async function health(): Promise<boolean> {
  try {
    const res = await fetch('/api/health')
    return res.ok
  } catch {
    return false
  }
}

// /analyze returns every stage's output; the frontend mostly needs `results`.
// Field-by-field shapes: contracts/*.sample.json and docs/DECISIONS.md.
// results.json (stage 5), docs/DECISIONS.md section 4.5.
export type PitchStatus = 'in_tune' | 'out_of_tune' | 'wrong_note' | 'skipped'
export type ResultNote = {
  id: string
  measure: number
  name: string
  lyric: string | null
  status: PitchStatus
  cents: number | null // negative = flat
  sang: string | null
  timing: 'on_time' | 'early' | 'late' | null
  timing_ms: number | null // positive = late
  sung_start_sec: number | null
  sung_end_sec: number | null
  uncertain: boolean
}
export type ResultExtra = {
  sid: string
  near_id: string
  sang: string
  during_rest: boolean
  start_sec: number
  end_sec: number
}
export type Results = {
  meta: {
    title: string
    mode: 'strict' | 'free'
    preset: string
    tempo_bpm: number
    octave_shift: number
    timing_offset_ms: number
  }
  score: { total: number; pitch: number; intonation: number; rhythm: number; completeness: number }
  counts: Record<string, number>
  notes: ResultNote[]
  extras: ResultExtra[]
  patterns: Record<string, unknown>
}

export type AnalyzeResponse = {
  results: Results
  expected_notes: any
  sung_notes: any
  pitch_track: any
}

// TODO(A): convert `audio` to WAV in the browser before sending (backend only reads WAV).
export async function analyze(musicxml: File, audio: Blob, settings: AnalyzeSettings): Promise<AnalyzeResponse> {
  if (MOCK_API) return (await import('./mockApi')).mockAnalyze(musicxml)
  const form = new FormData()
  form.append('musicxml', musicxml)
  form.append('audio', audio, 'performance.wav')
  form.append('mode', settings.mode)
  if (settings.tempoBpm !== undefined) form.append('tempo_bpm', String(settings.tempoBpm))
  form.append('preset', settings.preset ?? 'default')
  form.append('countin_end_sec', String(settings.countinEndSec ?? 0))

  const res = await fetch('/api/analyze', { method: 'POST', body: form })
  if (!res.ok) throw new Error(`/analyze failed: ${res.status}`)
  return res.json()
}

// feedback.json (stage 6), docs/DECISIONS.md section 4.6. /feedback always returns 200: on any LLM
// failure the backend sends the rule-based fallback in the same shape.
export type FeedbackTip = { title: string; explanation: string; exercise: string; measures: number[] }
export type Feedback = { source: 'llm' | 'fallback'; summary: string; strengths: string[]; tips: FeedbackTip[] }

export async function feedback(results: Results): Promise<Feedback> {
  if (MOCK_API) return (await import('./mockApi')).mockFeedback(results)
  const res = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  })
  if (!res.ok) throw new Error(`/feedback failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------------------------------
// Which calls the app makes. The backend isn't finished, so both are off: the UI shows a
// "not connected yet" note and makes no requests (no proxy errors).
// Flip a flag to true once its endpoint is finished.

/** Analyze a take (stages 1-5). Also needs WAV conversion before it can be turned on for real. */
const ANALYZE_CONNECTED = false
/** Instructor feedback (stage 6). */
const FEEDBACK_CONNECTED = false

/** `npm run dev:mock`: both calls return the contract samples, no network (see mockApi.ts). */
export const MOCK_API = import.meta.env.VITE_MOCK_API === '1'

export const ANALYZE_ENABLED = MOCK_API || ANALYZE_CONNECTED
export const FEEDBACK_ENABLED = MOCK_API || FEEDBACK_CONNECTED
