import { useEffect, useState } from 'react'
import { ColoredScore } from '../components/ColoredScore'
import { AudioPlayer } from '../components/desktop/AudioPlayer'
import { Icon } from '../components/desktop/Icon'
import { type Menu, MenuBar } from '../components/desktop/MenuBar'
import { DialogBox, Progress, Window } from '../components/desktop/Window'
import { FeedbackPanel } from '../components/FeedbackPanel'
import { type Grading, ScoreCard } from '../components/ScoreCard'
import type { Take } from '../hooks/useTakes'
import { downloadRecording } from '../lib/audio'
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

// The Results desktop: the Score window (colored score) on the left, the Results window (score card)
// and the Coach window on the right. Changing the grading (mode / level) re-analyzes; the previous
// results stay on screen until the new ones arrive.
export function Evaluate({ take, onBack, onHome }: { take: Take; onBack: () => void; onHome?: () => void }) {
  const [grading, setGrading] = useState<Grading>({ mode: 'free', preset: 'default' })
  const [status, setStatus] = useState<Status>(ANALYZE_ENABLED ? { state: 'loading' } : { state: 'off' })
  const [results, setResults] = useState<Results | null>(null)
  const [attempt, setAttempt] = useState(0) // bumped by "Try again"

  const changeGrading = (g: Grading) => {
    setGrading(g)
    setStatus({ state: 'loading' })
  }
  const retry = () => {
    setStatus({ state: 'loading' })
    setAttempt((n) => n + 1)
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
  }, [take, grading, attempt])

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
  const canAskCoach = FEEDBACK_ENABLED && !!results && status.state !== 'loading'

  // The tip whose bars are selected on the score (per feedback object: new feedback clears it).
  const [picked, setPicked] = useState<{ for: Feedback; index: number } | null>(null)
  const selectedTip = picked && picked.for === feedback ? picked.index : null
  const highlightBars = feedback && selectedTip !== null ? (feedback.tips[selectedTip]?.measures ?? []) : []

  const title = results?.meta.title || take.scoreName
  const firstLoad = !results

  const menus: Menu[] = [
    {
      label: 'File',
      items: [
        { label: 'Open another score…', onSelect: onBack },
        { label: 'Download this take…', onSelect: () => downloadRecording(take.blob, take.url, take.name, take.scoreName) },
        'separator',
        { label: 'Back to Practice', onSelect: onBack },
        ...(onHome ? ['separator' as const, { label: 'Welcome screen', onSelect: onHome }] : []),
      ],
    },
    { label: 'Take', items: [{ label: 'Sing it again', onSelect: onBack }] },
    {
      label: 'View',
      items: [
        { label: 'Practice', onSelect: onBack },
        { label: 'Results', checked: true },
      ],
    },
    {
      label: 'Coach',
      items: [
        { label: 'Get feedback', onSelect: requestFeedback, disabled: !canAskCoach || !!feedback || !!current?.loading },
        { label: 'Clear selected bars', onSelect: () => setPicked(null), disabled: selectedTip === null },
      ],
    },
  ]

  return (
    <div className="desk fit">
      <MenuBar menus={menus} />
      <main className="work-desk">
        <Window
          title={`${title} — ${take.name}`}
          className="score-window"
          toolbar={
            <>
              <AudioPlayer src={take.url} durationSec={take.durationMs / 1000} label={take.name} />
              {MOCK_API && <span className="toolbar-note">Mock API: made-up results, not your recording</span>}
              {!MOCK_API && status.state === 'loading' && results && <span className="toolbar-note">Re-scoring…</span>}
            </>
          }
        >
          <ColoredScore xml={take.scoreXml} results={results} highlightBars={highlightBars}>
            {status.state === 'off' && (
              <div className="dialog-holder">
                <DialogBox icon={<Icon name="caution" size={2} />} role="alert">
                  <p>Analysis isn't connected, so the notes aren't colored.</p>
                </DialogBox>
              </div>
            )}
            {status.state === 'loading' && firstLoad && (
              <div className="dialog-holder">
                <DialogBox icon={<Icon name="note" size={2} />}>
                  <p>Listening to {take.name} and checking every note…</p>
                  <Progress label="Analyzing your take" />
                </DialogBox>
              </div>
            )}
            {status.state === 'failed' && (
              <div className="dialog-holder">
                <DialogBox
                  icon={<Icon name="caution" size={2} />}
                  role="alert"
                  actions={
                    <>
                      <button type="button" className="button" onClick={onBack}>
                        Back to Practice
                      </button>
                      <button type="button" className="button default" onClick={retry}>
                        Try again
                      </button>
                    </>
                  }
                >
                  <p>
                    <b>The analysis didn't finish.</b>
                  </p>
                  <p>{status.error}</p>
                </DialogBox>
              </div>
            )}
          </ColoredScore>
        </Window>

        <Window
          title="Results"
          className="results-window"
          footer={
            <button type="button" className="button" onClick={onBack}>
              Sing it again
            </button>
          }
        >
          {results ? (
            <ScoreCard results={results} grading={grading} onGradingChange={changeGrading} busy={status.state === 'loading'} />
          ) : (
            <p className="score-meta">{status.state === 'failed' ? 'No score yet.' : 'Scoring your take…'}</p>
          )}
        </Window>

        <Window title="Coach" className={`coach-window${feedback ? '' : ' compact'}`}>
          <FeedbackPanel
            feedback={feedback}
            loading={current?.loading ?? false}
            failed={current?.failed ?? false}
            onRequest={canAskCoach ? requestFeedback : undefined}
            selectedTip={selectedTip}
            onSelectTip={(index) => setPicked(feedback && index !== null ? { for: feedback, index } : null)}
          />
        </Window>
      </main>
    </div>
  )
}
