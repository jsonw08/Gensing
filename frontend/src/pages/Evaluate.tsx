import { useEffect, useState } from 'react'
import { FeedbackPanel } from '../components/FeedbackPanel'
import { ScoreView } from '../components/ScoreView'
import type { Take } from '../hooks/useTakes'
import { EVALUATE_ENDPOINT, type Feedback, feedback as fetchFeedback } from '../lib/api'

// Same layout as Practice: score on the left, the instructor's feedback where the recorder was.
export function Evaluate({ take, onBack }: { take: Take; onBack: () => void }) {
  // TODO: once EVALUATE_ENDPOINT exists, send the take (as WAV) + score, color the score from
  // results.notes, and store the results here.
  const results: unknown = null

  const [feedback, setFeedback] = useState<Feedback | null>(null)

  // /feedback is a separate call so the colored score can show before the AI text is ready.
  // It always returns 200 (rule-based fallback on any LLM failure).
  useEffect(() => {
    if (!results) return
    let cancelled = false
    fetchFeedback(results)
      .then((fb) => !cancelled && setFeedback(fb))
      .catch((err) => console.error('[feedback]', err))
    return () => {
      cancelled = true
    }
  }, [results])

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
          {!EVALUATE_ENDPOINT && (
            <p className="eval-note">Analysis isn't connected yet, so the notes aren't colored.</p>
          )}
          <ScoreView xml={take.scoreXml} />
        </section>

        <aside className="side-panel">
          <FeedbackPanel takeName={take.name} feedback={feedback} loading={!!results && !feedback} />
        </aside>
      </div>
    </main>
  )
}
