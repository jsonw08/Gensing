import { useMemo, useRef, useState } from 'react'
import { BlurredSheet } from '../components/BlurredSheet'
import { ScoreView } from '../components/ScoreView'
import { useRecorder } from '../hooks/useRecorder'
import { audioDurationMs, isPlayableAudio } from '../lib/audio'
import { countInFor, DEFAULT_TEMPO_BPM, readScoreTiming } from '../lib/scoreInfo'
import type { Take, useTakes } from '../hooks/useTakes'

export type Score = { file: File; xml: string }

function formatTime(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}.${Math.floor((ms % 1000) / 100)}`
}

// Score and saved takes live in App, so they survive a trip to the Evaluate page and back.
export function Practice({
  score,
  onScoreChange,
  takes,
  onEvaluate,
  onBack,
}: {
  score: Score | null
  onScoreChange: (score: Score) => void
  takes: ReturnType<typeof useTakes>
  onEvaluate: (take: Take) => void
  onBack: () => void
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const rec = useRecorder()
  const scoreXml = score?.xml ?? null

  // Starting tempo: the score's marking, editable. One bar of count-in clicks at this tempo.
  const timing = useMemo(() => (scoreXml ? readScoreTiming(scoreXml) : null), [scoreXml])
  const [tempo, setTempo] = useState(() => timing?.tempoBpm ?? DEFAULT_TEMPO_BPM)
  const [tempoText, setTempoText] = useState(String(tempo))
  const countIn = timing ? countInFor(timing, tempo) : undefined
  const startRecording = () => rec.start(countIn)

  function changeTempo(text: string) {
    setTempoText(text)
    const bpm = Number(text)
    if (bpm >= 30 && bpm <= 240) setTempo(Math.round(bpm))
  }

  // An uploaded recording becomes a take of the current score, named after the file.
  async function uploadTakes(files: File[]) {
    if (!files.length || !score) return
    setUploadError(null)
    const rejected: string[] = []
    for (const file of files) {
      if (!(await isPlayableAudio(file))) {
        rejected.push(file.name)
        continue
      }
      const name = file.name.replace(/\.[^.]+$/, '') || file.name
      takes.add({ blob: file, durationMs: await audioDurationMs(file), scoreName: score.file.name, scoreXml: score.xml, name })
    }
    if (rejected.length) setUploadError(`Couldn't play ${rejected.join(', ')}. Try a WAV, MP3, M4A or WebM file.`)
  }

  function saveTake() {
    if (!rec.blob || !score) return
    takes.add({
      blob: rec.blob,
      durationMs: rec.elapsedMs,
      scoreName: score.file.name,
      scoreXml: score.xml,
      tempoBpm: tempo,
      countinEndSec: rec.countinEndSec,
    })
    rec.reset() // ready for the next take
  }

  async function chooseFile(file: File | undefined) {
    if (!file) return
    rec.reset() // a take belongs to one score
    const xml = await file.text()
    const bpm = readScoreTiming(xml).tempoBpm
    setTempo(bpm)
    setTempoText(String(bpm))
    onScoreChange({ file, xml })
  }

  const busy = rec.status === 'countin' || rec.status === 'recording'

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
          className={`sheet-stage${dragging ? ' dragging' : ''}${scoreXml ? ' loaded' : ''}${rec.status === 'recording' ? ' is-recording' : ''}`}
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
                <span className="file-name">{score?.file.name}</span>
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

        {/* Count-in: big beat numbers over the page; then a short "Sing!" so the start is unmistakable. */}
        {rec.status === 'countin' && countIn && (
          <div className="countin-overlay" aria-live="assertive">
            <div className="countin-card">
              <span className="countin-label">Get ready · ♩ = {tempo}</span>
              <span key={rec.countInBeat} className="countin-beat">
                {rec.countInBeat || '…'}
              </span>
              <span className="countin-dots">
                {Array.from({ length: countIn.beats }, (_, i) => (
                  <i key={i} className={i < rec.countInBeat ? 'on' : ''} />
                ))}
              </span>
            </div>
          </div>
        )}
        {rec.status === 'recording' && rec.elapsedMs < 1200 && (
          <div className="countin-overlay" aria-live="assertive">
            <div className="countin-card go">
              <span className="countin-beat">● Sing!</span>
              <span className="countin-label">Recording</span>
            </div>
          </div>
        )}

        <aside className="side-panel">
          <section className={`recorder${busy ? ' is-busy' : ''}`} aria-live="polite">
            <div className="rec-status">
              <span className={`rec-dot ${rec.status}`} />
              <span className="rec-label">
                {rec.status === 'idle' && (scoreXml ? 'Ready to record' : 'Choose a score to start')}
                {rec.status === 'countin' && `Count-in… ${rec.countInBeat || ''}`}
                {rec.status === 'recording' && 'Recording'}
                {rec.status === 'stopped' && 'Take recorded'}
              </span>
              <span className="rec-time">{formatTime(rec.elapsedMs)}</span>
            </div>

            <div className="tempo-row">
              <label>
                Tempo ♩ =
                <input
                  type="number"
                  min={30}
                  max={240}
                  value={tempoText}
                  onChange={(e) => changeTempo(e.target.value)}
                  onBlur={() => setTempoText(String(tempo))}
                  disabled={!scoreXml || busy}
                />
                bpm
              </label>
              {countIn && (
                <span className="tempo-hint">
                  {countIn.beats}-beat count-in{timing && tempo !== timing.tempoBpm ? ` · score says ${timing.tempoBpm}` : ''}
                </span>
              )}
            </div>

            <div className="rec-controls">
              {rec.status === 'idle' && (
                <button className="btn btn-record" onClick={startRecording} disabled={!scoreXml}>
                  ● Start recording
                </button>
              )}
              {busy && (
                <button className="btn btn-secondary" onClick={rec.stop}>
                  ■ Stop
                </button>
              )}
              {rec.status === 'stopped' && (
                <button className="btn btn-primary" onClick={saveTake} title="Keep this take">
                  ✓ Save take
                </button>
              )}
              {rec.status !== 'idle' && (
                <button className="btn btn-ghost" onClick={() => rec.restart(countIn)}>
                  ↺ Restart
                </button>
              )}
            </div>

            {rec.error && <p className="rec-error">{rec.error}</p>}
            {rec.url && <audio className="take" controls src={rec.url} />}
          </section>

          <section className="takes">
            <div className="takes-head">
              <h3>Saved takes</h3>
              <input
                ref={uploadRef}
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg"
                multiple
                hidden
                onChange={(e) => {
                  uploadTakes([...(e.target.files ?? [])]) // copy first: clearing the input empties the FileList
                  e.target.value = '' // allow uploading the same file again
                }}
              />
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => uploadRef.current?.click()}
                disabled={!score}
                title={score ? 'Add a recording from a file' : 'Choose a score first'}
              >
                ⇪ Upload
              </button>
            </div>
            {uploadError && <p className="rec-error">{uploadError}</p>}
            {takes.takes.length === 0 ? (
              <p className="takes-empty">No saved takes yet. Record one and press Save take, or upload a recording.</p>
            ) : (
              <ul>
                {takes.takes.map((t) => (
                  <li key={t.id} className="take-row">
                    <div className="take-info">
                      <span className="take-name">{t.name}</span>
                      <span className="take-meta">
                        {t.scoreName} · {t.durationMs ? formatTime(t.durationMs) : '–'} ·{' '}
                        {t.savedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                      </span>
                    </div>
                    <audio controls src={t.url} />
                    <div className="take-actions">
                      <button className="btn btn-primary btn-sm" onClick={() => onEvaluate(t)}>
                        Evaluate
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => takes.remove(t)}>
                        Delete
                      </button>
                    </div>
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
