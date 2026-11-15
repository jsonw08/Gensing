import { useEffect, useState } from 'react'
import { ColoredScore } from '../components/ColoredScore'
import { FeedbackPanel } from '../components/FeedbackPanel'
import { type Grading, ScoreCard } from '../components/ScoreCard'
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

type Status = { state: 'off' } | { state: 'loading' } | { state: 'done' } | { state: 'failed'; error: string }

// Same layout as Practice: score on the left, score card + the instructor's feedback where the recorder was.
// Changing the grading (mode / level) re-analyzes; the previous results stay on screen until the new ones arrive.
export function Evaluate({ take, onBack }: { take: Take; onBack: () => void }) {
  const [grading, setGrading] = useState<Grading>({ mode: 'free', preset: 'default' })
  const [status, setStatus] = useState<Status>(ANALYZE_ENABLED ? { state: 'loading' } : { state: 'off' })
  const [results, setResults] = useState<Results | null>(null)

  const changeGrading = (g: Grading) => {
    setGrading(g)
    setStatus({ state: 'loading' })
  }

  // Stages 1-5, with the tempo it was sung at and where beat 1 is (after the count-in; 0 for uploads).
  useEffect(() => {
    if (!ANALYZE_ENABLED) return
    let cancelled = false
    const score = new File([take.scoreXml], take.scoreName, { type: 'application/xml' })
    analyze(score, take.blob, {
      mode: grading.mode,
      preset: grading.preset,
      tempoBpm: take.tempoBpm ?? undefined,
      countinEndSec: take.countinEndSec,
    })
      .then((res) => {
        if (cancelled) return
        setResults(res.results)
        setStatus({ state: 'done' })
      })
      .catch((err) => !cancelled && setStatus({ state: 'failed', error: err instanceof Error ? err.message : String(err) }))
    return () => {
      cancelled = true
    }
  }, [take, grading])

  // /feedback (the coach) runs only when the user clicks "Get feedback". It always returns 200 (rule-based
  // fallback on any LLM failure). Answers are kept per results object, so a re-graded take never shows
  // the previous grading's tips: the button comes back instead.
  const [fb, setFb] = useState<{ for: Results; feedback: Feedback | null; loading: boolean; failed: boolean } | null>(null)
  const requestFeedback = () => {
    if (!results) return
    const r = results
    setFb({ for: r, feedback: null, loading: true, failed: false })
    fetchFeedback(r)
      .then((feedback) => setFb((cur) => (cur?.for === r ? { for: r, feedback, loading: false, failed: false } : cur)))
      .catch((err) => {
        console.error('[feedback]', err)
        setFb((cur) => (cur?.for === r ? { for: r, feedback: null, loading: false, failed: true } : cur))
      })
  }
  const current = fb && fb.for === results ? fb : null
  const feedback = current?.feedback ?? null

  // The tip whose bars are outlined on the score (per feedback object: new feedback clears it).
  const [picked, setPicked] = useState<{ for: Feedback; index: number } | null>(null)
  const selectedTip = picked && picked.for === feedback ? picked.index : null
  const highlightBars = feedback && selectedTip !== null ? (feedback.tips[selectedTip]?.measures ?? []) : []

  const note =
    status.state === 'off'
      ? "Analysis isn't connected, so the notes aren't colored."
      : status.state === 'loading' && !results
        ? 'Analyzing your take…'
        : status.state === 'failed'
          ? `Analysis failed: ${status.error}`
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
          <ColoredScore xml={take.scoreXml} results={results} highlightBars={highlightBars} />
        </section>

        <aside className="side-panel">
          {results && (
            <ScoreCard
              results={results}
              grading={grading}
              onGradingChange={changeGrading}
              busy={status.state === 'loading'}
            />
          )}
          <FeedbackPanel
            takeName={take.name}
            feedback={feedback}
            loading={current?.loading ?? false}
            failed={current?.failed ?? false}
            onRequest={FEEDBACK_ENABLED && results && status.state !== 'loading' ? requestFeedback : undefined}
            selectedTip={selectedTip}
            onSelectTip={(index) => setPicked(feedback && index !== null ? { for: feedback, index } : null)}
          />
        </aside>
      </div>
    </main>
  )
}
