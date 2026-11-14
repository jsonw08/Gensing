import { useRef, useState } from 'react'
import { BlurredSheet } from '../components/BlurredSheet'
import { ScoreView } from '../components/ScoreView'
import { useRecorder } from '../hooks/useRecorder'
import { type Take, useTakes } from '../hooks/useTakes'

// TEMP: placeholder until the FastAPI evaluate endpoint exists. Swap in the real path
// (e.g. '/api/analyze' via lib/api.ts) once it's wired up.
const EVALUATE_ENDPOINT: string | null = null

function formatTime(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}.${Math.floor((ms % 1000) / 100)}`
}

export function Practice({ onBack }: { onBack: () => void }) {
  const [scoreFile, setScoreFile] = useState<File | null>(null)
  const [scoreXml, setScoreXml] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const rec = useRecorder()
  const takes = useTakes()

  // Take ids the user has asked to evaluate (shows a note under the row until the endpoint exists).
  const [evaluateRequested, setEvaluateRequested] = useState<Set<number>>(new Set())

  function evaluateTake(take: Take) {
    if (!EVALUATE_ENDPOINT) {
      console.info('[evaluate] no endpoint yet; would send', take.name, take.blob)
      setEvaluateRequested((prev) => new Set(prev).add(take.id))
      return
    }
    // TODO: POST the take (as WAV) + score to EVALUATE_ENDPOINT and show the results.
  }

  function saveTake() {
    if (!rec.blob || !scoreFile) return
    takes.add(rec.blob, rec.elapsedMs, scoreFile.name)
    rec.reset() // ready for the next take
  }

  async function chooseFile(file: File | undefined) {
    if (!file) return
    rec.reset() // a take belongs to one score
    setScoreFile(file)
    setScoreXml(await file.text())
  }

  const busy = rec.status === 'recording'

  return (
    <main className="practice">
      <header className="topbar">
        <button className="btn btn-ghost" onClick={onBack} disabled={busy}>
          ← Back
        </button>
        <span className="brand-sm">Gensing</span>
      </header>

      <div className="practice-layout">
        <section
          className={`sheet-stage${dragging ? ' dragging' : ''}${scoreXml ? ' loaded' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            if (!busy) chooseFile(e.dataTransfer.files?.[0])
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".musicxml,.xml,.mxl"
            hidden
            onChange={(e) => {
              chooseFile(e.target.files?.[0])
              e.target.value = '' // allow re-choosing the same file
            }}
          />

          {scoreXml ? (
            <>
              <div className="file-bar">
                <span className="file-name">{scoreFile?.name}</span>
                <button className="btn btn-ghost btn-sm" onClick={() => inputRef.current?.click()} disabled={busy}>
                  Change file
                </button>
              </div>
              <ScoreView xml={scoreXml} />
            </>
          ) : (
            <>
              <BlurredSheet />
              <div className="chooser">
                <h2>Choose your score</h2>
                <p>Pick a MusicXML file (.musicxml, .xml, .mxl), or drop it here.</p>
                <button className="btn btn-primary" onClick={() => inputRef.current?.click()}>
                  Choose file
                </button>
              </div>
            </>
          )}
        </section>

        <aside className="side-panel">
          <section className="recorder" aria-live="polite">
            <div className="rec-status">
              <span className={`rec-dot ${rec.status}`} />
              <span className="rec-label">
                {rec.status === 'idle' && (scoreXml ? 'Ready to record' : 'Choose a score to start')}
                {rec.status === 'recording' && 'Recording'}
                {rec.status === 'stopped' && 'Take recorded'}
              </span>
              <span className="rec-time">{formatTime(rec.elapsedMs)}</span>
            </div>

            <div className="rec-controls">
              {rec.status === 'idle' && (
                <button className="btn btn-record" onClick={rec.start} disabled={!scoreXml}>
                  ● Start recording
                </button>
              )}
              {busy && (
                <button className="btn btn-secondary" onClick={rec.stop}>
                  ■ Stop
                </button>
              )}
              {rec.status !== 'idle' && (
                <button className="btn btn-ghost" onClick={rec.restart}>
                  ↺ Restart
                </button>
              )}
              {rec.status === 'stopped' && (
                <button className="btn btn-primary" onClick={saveTake} title="Keep this take">
                  ✓ Save take
                </button>
              )}
            </div>

            {rec.error && <p className="rec-error">{rec.error}</p>}
            {rec.url && <audio className="take" controls src={rec.url} />}
          </section>

          <section className="takes">
            <h3>Saved takes</h3>
            {takes.takes.length === 0 ? (
              <p className="takes-empty">No saved takes yet. Record one and press Save take.</p>
            ) : (
              <ul>
                {takes.takes.map((t) => (
                  <li key={t.id} className="take-row">
                    <div className="take-info">
                      <span className="take-name">{t.name}</span>
                      <span className="take-meta">
                        {t.scoreName} · {formatTime(t.durationMs)} ·{' '}
                        {t.savedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                      </span>
                    </div>
                    <audio controls src={t.url} />
                    <div className="take-actions">
                      <button className="btn btn-primary btn-sm" onClick={() => evaluateTake(t)}>
                        Evaluate
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => takes.remove(t)}>
                        Delete
                      </button>
                    </div>
                    {evaluateRequested.has(t.id) && (
                      <p className="take-note">Evaluation isn't connected yet (no endpoint).</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </main>
  )
}
