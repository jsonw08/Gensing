import { useEffect, useState } from 'react'
import { ColoredScore } from '../components/ColoredScore'
import { FeedbackPanel } from '../components/FeedbackPanel'
import type { Take } from '../hooks/useTakes'
import {
  analyze,
  ANALYZE_ENABLED,
  type Feedback,
  feedback as fetchFeedback,
  FEEDBACK_ENABLED,
  MOCK_API,
  type Results,
} from '../lib/api'

type Analysis = { state: 'off' } | { state: 'loading' } | { state: 'done'; results: Results } | { state: 'failed'; error: string }

// Same layout as Practice: score on the left, the instructor's feedback where the recorder was.
export function Evaluate({ take, onBack }: { take: Take; onBack: () => void }) {
  const [analysis, setAnalysis] = useState<Analysis>(ANALYZE_ENABLED ? { state: 'loading' } : { state: 'off' })
  const results = analysis.state === 'done' ? analysis.results : null

  // Stages 1-5, with the tempo it was sung at and where beat 1 is (after the count-in; 0 for uploads).
  useEffect(() => {
    if (!ANALYZE_ENABLED) return
    let cancelled = false
    const score = new File([take.scoreXml], take.scoreName, { type: 'application/xml' })
    analyze(score, take.blob, { mode: 'strict', tempoBpm: take.tempoBpm ?? undefined, countinEndSec: take.countinEndSec })
      .then((res) => !cancelled && setAnalysis({ state: 'done', results: res.results }))
      .catch((err) => !cancelled && setAnalysis({ state: 'failed', error: String(err) }))
    return () => {
      cancelled = true
    }
  }, [take])

  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [feedbackFailed, setFeedbackFailed] = useState(false)

  // /feedback is a separate call so the colored score shows before the AI text is ready.
  // It always returns 200 (rule-based fallback on any LLM failure).
  useEffect(() => {
    if (!results || !FEEDBACK_ENABLED) return
    let cancelled = false
    fetchFeedback(results)
      .then((fb) => !cancelled && setFeedback(fb))
      .catch((err) => {
        console.error('[feedback]', err)
        if (!cancelled) setFeedbackFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [results])

  const note =
    analysis.state === 'off'
      ? "Analysis isn't connected yet, so the notes aren't colored."
      : analysis.state === 'loading'
        ? 'Analyzing your take…'
        : analysis.state === 'failed'
          ? `Analysis failed: ${analysis.error}`
          : MOCK_API
            ? 'Mock API: showing made-up results for this score, not your recording.'
            : null

  return (
    <main className="practice">
      <header className="topbar">
        <button className="btn btn-ghost" onClick={onBack}>
          ← Back to practice
        </button>
        <span className="brand-sm">Gensing</span>
      </header>

      <div className="practice-layout">
        <section className="sheet-stage loaded">
          <div className="file-bar">
            <span className="file-name">
              {take.name} · {take.scoreName}
            </span>
            <audio className="file-audio" controls src={take.url} />
          </div>
          {note && <p className="eval-note">{note}</p>}
          <ColoredScore key={results ? 'colored' : 'plain'} xml={take.scoreXml} results={results} />
        </section>

        <aside className="side-panel">
          <FeedbackPanel
            takeName={take.name}
            feedback={feedback}
            loading={FEEDBACK_ENABLED && analysis.state !== 'off' && analysis.state !== 'failed' && !feedback && !feedbackFailed}
            failed={feedbackFailed}
          />
        </aside>
      </div>
    </main>
  )
}
