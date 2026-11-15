import type React from 'react'
import type { Feedback } from '../lib/api'

// Read-only coaching feedback for one take (feedback.json from /feedback). No replies.
// The coach is only asked when the user clicks "Get feedback" (`onRequest`), not on every analysis.
// A tip that names bars can be clicked: its bars are outlined on the score (click again to clear).
export function FeedbackPanel({
  takeName,
  feedback,
  loading,
  failed = false,
  selectedTip = null,
  onSelectTip,
  onRequest,
}: {
  takeName: string
  feedback: Feedback | null
  loading: boolean
  failed?: boolean
  /** Ask the coach; when missing (nothing analyzed yet, or feedback switched off) there's no button. */
  onRequest?: () => void
  selectedTip?: number | null
  onSelectTip?: (index: number | null) => void
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
          <div className="feedback-empty">
            <p>
              {loading
                ? 'Listening to your take…'
                : failed
                  ? "Couldn't get feedback. Is the backend running?"
                  : onRequest
                    ? 'Get a short summary and practice tips for this take.'
                    : 'Feedback will be available once your take has been analyzed.'}
            </p>
            {onRequest && !loading && (
              <button className="btn btn-primary btn-sm" onClick={onRequest}>
                {failed ? 'Try again' : 'Get feedback'}
              </button>
            )}
          </div>
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
                  {feedback.tips.map((tip, i) => {
                    const clickable = !!onSelectTip && tip.measures.length > 0
                    const select = () => onSelectTip?.(selectedTip === i ? null : i)
                    return (
                      <li
                        key={i}
                        className={`tip${clickable ? ' clickable' : ''}${selectedTip === i ? ' selected' : ''}`}
                        {...(clickable && {
                          role: 'button',
                          tabIndex: 0,
                          'aria-pressed': selectedTip === i,
                          title: selectedTip === i ? 'Hide on the score' : 'Show on the score',
                          onClick: select,
                          onKeyDown: (e: React.KeyboardEvent) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              select()
                            }
                          },
                        })}
                      >
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
                    )
                  })}
                </ol>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
