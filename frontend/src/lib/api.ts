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
export type AnalyzeResponse = {
  results: any
  expected_notes: any
  sung_notes: any
  pitch_track: any
}

// TODO(A): convert `audio` to WAV in the browser before sending (backend only reads WAV).
export async function analyze(musicxml: File, audio: Blob, settings: AnalyzeSettings): Promise<AnalyzeResponse> {
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

export async function feedback(results: unknown): Promise<Feedback> {
  const res = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  })
  if (!res.ok) throw new Error(`/feedback failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------------------------------
// TEMP placeholders: endpoints the frontend needs that the backend doesn't have yet. `null` = not
// connected; the UI shows a "not connected yet" note instead of calling anything.

/** Analyze a take (stages 1-5). Will become '/api/analyze' once WAV conversion is in. */
export const EVALUATE_ENDPOINT: string | null = null
