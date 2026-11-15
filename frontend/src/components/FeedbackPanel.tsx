import type { Feedback } from '../lib/api'

// Read-only coaching feedback for one take (feedback.json from /feedback). No replies.
export function FeedbackPanel({
  takeName,
  feedback,
  loading,
  failed = false,
}: {
  takeName: string
  feedback: Feedback | null
  loading: boolean
  failed?: boolean
}) {
  return (
    <section className="feedback" aria-live="polite">
      <header className="feedback-head">
        <span className="feedback-avatar" aria-hidden="true">
          ♪
        </span>
        <div>
          <h3>Instructor feedback</h3>
          <span className="feedback-sub">
            {takeName}
            {feedback?.source === 'fallback' && ' · quick tips (AI unavailable)'}
          </span>
        </div>
      </header>

      <div className="feedback-body">
        {!feedback ? (
          <p className="feedback-empty">
            {failed
              ? "Couldn't load feedback. Is the backend running?"
              : loading
                ? 'Listening to your take…'
                : 'Feedback will appear here once your take has been analyzed.'}
          </p>
        ) : (
          <>
            <p className="feedback-summary">{feedback.summary}</p>

            {feedback.strengths.length > 0 && (
              <div>
                <h4>What went well</h4>
                <ul className="feedback-strengths">
                  {feedback.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {feedback.tips.length > 0 && (
              <div>
                <h4>What to work on</h4>
                <ol className="feedback-tips">
                  {feedback.tips.map((tip, i) => (
                    <li key={i} className="tip">
                      <p className="tip-title">{tip.title}</p>
                      <p>{tip.explanation}</p>
                      <p className="tip-exercise">
                        <strong>Try this:</strong> {tip.exercise}
                      </p>
                      {tip.measures.length > 0 && (
                        <div className="tip-bars">
                          {tip.measures.map((m) => (
                            <span key={m}>Bar {m}</span>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
