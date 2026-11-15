import type React from 'react'
import type { Feedback } from '../lib/api'
import { Icon } from './desktop/Icon'
import { Progress } from './desktop/Window'

// The Coach window's contents: coaching for one take (feedback.json from /feedback). No replies.
// The coach is only asked when the user clicks "Get feedback" (`onRequest`), not on every analysis.
// A tip that names bars can be clicked: its bars are selected on the score (click again to clear).
export function FeedbackPanel({
  feedback,
  loading,
  failed = false,
  selectedTip = null,
  onSelectTip,
  onRequest,
}: {
  feedback: Feedback | null
  loading: boolean
  failed?: boolean
  /** Ask the coach; when missing (nothing analyzed yet, or feedback switched off) there's no button. */
  onRequest?: () => void
  selectedTip?: number | null
  onSelectTip?: (index: number | null) => void
}) {
  if (!feedback) {
    return (
      <div className="coach-intro" aria-live="polite">
        <Icon name={failed ? 'caution' : 'note'} size={2} />
        <div className="coach-intro-text">
          <p>
            {loading
              ? 'Listening to your take…'
              : failed
                ? "Couldn't reach the coach. Check that the backend is running, then try again."
                : onRequest
                  ? 'Get a short summary of this take and a few things to practice.'
                  : 'The coach can comment once your take has been analyzed.'}
          </p>
          {loading && <Progress label="Getting feedback" />}
          {onRequest && !loading && (
            <button type="button" className="button default" onClick={onRequest}>
              {failed ? 'Try again' : 'Get feedback'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <>
      {feedback.source === 'fallback' && <p className="coach-source">Quick tips: the AI coach is offline right now.</p>}
      <p className="coach-summary">{feedback.summary}</p>

      {feedback.strengths.length > 0 && (
        <div>
          <h3>What went well</h3>
          <ul className="coach-strengths">
            {feedback.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {feedback.tips.length > 0 && (
        <div>
          <h3>What to work on</h3>
          <ol className="coach-tips">
            {feedback.tips.map((tip, i) => {
              const clickable = !!onSelectTip && tip.measures.length > 0
              const selected = selectedTip === i
              const select = () => onSelectTip?.(selected ? null : i)
              return (
                <li
                  key={i}
                  className={`coach-tip${clickable ? ' clickable' : ''}${selected ? ' selected' : ''}`}
                  {...(clickable && {
                    role: 'button',
                    tabIndex: 0,
                    'aria-pressed': selected,
                    title: selected ? 'Clear the selection on the score' : 'Select these bars on the score',
                    onClick: select,
                    onKeyDown: (e: React.KeyboardEvent) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        select()
                      }
                    },
                  })}
                >
                  <p className="coach-tip-title">{tip.title}</p>
                  <p>{tip.explanation}</p>
                  <p>
                    <b>Try this:</b> {tip.exercise}
                  </p>
                  {tip.measures.length > 0 && (
                    <div className="coach-tip-bars">
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
  )
}
