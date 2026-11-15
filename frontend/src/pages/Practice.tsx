import { useEffect, useMemo, useRef, useState } from 'react'
import { AudioPlayer } from '../components/desktop/AudioPlayer'
import { Icon } from '../components/desktop/Icon'
import { type Menu, MenuBar } from '../components/desktop/MenuBar'
import { DialogBox, Window } from '../components/desktop/Window'
import { ScoreView } from '../components/ScoreView'
import { useRecorder } from '../hooks/useRecorder'
import type { Take, useTakes } from '../hooks/useTakes'
import { audioDurationMs, downloadRecording, isPlayableAudio } from '../lib/audio'
import { countInFor, DEFAULT_TEMPO_BPM, readScoreTiming, readScoreTitle } from '../lib/scoreInfo'

export type Score = { file: File; xml: string }

/** 0:00.0 (minutes, seconds, tenths). */
function formatTime(ms: number): string {
  const total = Math.floor(ms / 1000)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}.${Math.floor((ms % 1000) / 100)}`
}
const shortLength = (ms: number) => (ms ? formatTime(ms).replace(/\.\d$/, '') : '–')

// The Practice desktop: the Score window (the open score) on the left, the Recorder and the list of
// saved Takes on the right. The count-in runs as a dialog over the desktop.
// Score and saved takes live in App, so they survive a trip to the Results screen and back.
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
  const scoreInputRef = useRef<HTMLInputElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const rec = useRecorder()
  const scoreXml = score?.xml ?? null
  const title = useMemo(() => (scoreXml ? readScoreTitle(scoreXml) : null), [scoreXml])

  // Starting tempo: the score's marking, editable. One bar of count-in clicks at this tempo.
  const timing = useMemo(() => (scoreXml ? readScoreTiming(scoreXml) : null), [scoreXml])
  const [tempo, setTempo] = useState(() => timing?.tempoBpm ?? DEFAULT_TEMPO_BPM)
  const [tempoText, setTempoText] = useState(String(tempo))
  const countIn = timing ? countInFor(timing, tempo) : undefined
  const busy = rec.status === 'countin' || rec.status === 'recording'

  // Turn the mic on as soon as there's a score to sing, so it's settled before the first count-in.
  const { warmMic } = rec
  useEffect(() => {
    if (scoreXml) warmMic()
  }, [scoreXml, warmMic])

  // The selected take: the one clicked, until a newer take is saved or uploaded (then the newest).
  const newestId = takes.takes[0]?.id ?? null
  const [picked, setPicked] = useState<{ id: number; whenNewest: number | null } | null>(null)
  const pickedTake = picked && picked.whenNewest === newestId ? takes.takes.find((t) => t.id === picked.id) : undefined
  const selected = pickedTake ?? takes.takes[0] ?? null
  const selectedId = selected?.id ?? null
  const setSelectedId = (id: number) => setPicked({ id, whenNewest: newestId })

  function changeTempo(text: string) {
    setTempoText(text)
    const bpm = Number(text)
    if (bpm >= 30 && bpm <= 240) setTempo(Math.round(bpm))
  }

  async function chooseFile(file: File | undefined) {
    if (!file || busy) return
    rec.reset() // a take belongs to one score
    const xml = await file.text()
    const bpm = readScoreTiming(xml).tempoBpm
    setTempo(bpm)
    setTempoText(String(bpm))
    onScoreChange({ file, xml })
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

  const download = (t: Take) => downloadRecording(t.blob, t.url, t.name, t.scoreName)
  const record = () => rec.start(countIn)
  const startOver = () => rec.restart(countIn)

  const menus: Menu[] = [
    {
      label: 'File',
      items: [
        { label: 'Open score…', onSelect: () => scoreInputRef.current?.click(), disabled: busy },
        { label: 'Upload recording…', onSelect: () => uploadRef.current?.click(), disabled: !score || busy },
        { label: 'Download selected take…', onSelect: () => selected && download(selected), disabled: !selected },
        'separator',
        { label: 'Welcome screen', onSelect: onBack, disabled: busy },
      ],
    },
    {
      label: 'Take',
      items: [
        { label: 'Record', onSelect: record, disabled: !score || rec.status !== 'idle' },
        { label: 'Stop', onSelect: rec.stop, disabled: !busy },
        { label: 'Save take', onSelect: saveTake, disabled: rec.status !== 'stopped' },
        { label: 'Start over', onSelect: startOver, disabled: rec.status === 'idle' },
        'separator',
        { label: 'Evaluate selected take', onSelect: () => selected && onEvaluate(selected), disabled: !selected || busy },
        { label: 'Delete selected take', onSelect: () => selected && takes.remove(selected), disabled: !selected || busy },
      ],
    },
    {
      label: 'View',
      items: [
        { label: 'Practice', checked: true },
        { label: 'Results', onSelect: () => selected && onEvaluate(selected), disabled: !selected || busy },
      ],
    },
  ]

  const status =
    rec.status === 'idle'
      ? scoreXml
        ? 'Ready to record'
        : 'Open a score first'
      : rec.status === 'countin'
        ? 'Count-in…'
        : rec.status === 'recording'
          ? 'Recording'
          : 'Take recorded'

  return (
    <div className="desk fit">
      <MenuBar menus={menus} />
      <input
        ref={scoreInputRef}
        type="file"
        accept=".musicxml,.xml,.mxl"
        hidden
        onChange={(e) => {
          chooseFile(e.target.files?.[0])
          e.target.value = '' // allow re-choosing the same file
        }}
      />
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

      <main className="work-desk">
        <Window
          title={score ? (title ?? score.file.name) : 'No score open'}
          className="score-window"
          toolbar={
            score && (
              <>
                <button type="button" className="button" onClick={() => scoreInputRef.current?.click()} disabled={busy}>
                  Open score…
                </button>
                <span className="toolbar-note">{score.file.name}</span>
              </>
            )
          }
        >
          <div
            className={`score-page well${dragging ? ' dropping' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              if (!busy) setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              chooseFile(e.dataTransfer.files?.[0])
            }}
          >
            {scoreXml ? (
              <ScoreView xml={scoreXml} />
            ) : (
              <div className="dialog-holder">
                <DialogBox
                  icon={<Icon name="note" size={2} />}
                  actions={
                    <button type="button" className="button default" onClick={() => scoreInputRef.current?.click()}>
                      Open score…
                    </button>
                  }
                >
                  <p>
                    <b>Open a score to start.</b>
                  </p>
                  <p>Choose a MusicXML file (.musicxml, .xml or .mxl), or drop one on this window.</p>
                </DialogBox>
              </div>
            )}
          </div>
        </Window>

        <Window title="Recorder" className="recorder-window">
          <div className="counter" aria-live="polite">
            <span className={`lamp ${rec.status}`} aria-hidden="true" />
            <span className="counter-label">{status}</span>
            <span className="counter-time">{formatTime(rec.elapsedMs)}</span>
          </div>

          <div className="tempo-row">
            <label>
              Tempo ♩ =
              <input
                className="field"
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

          <div className="button-row">
            {rec.status === 'idle' && (
              <button type="button" className="button default" onClick={record} disabled={!scoreXml}>
                Record
              </button>
            )}
            {busy && (
              <button type="button" className="button default" onClick={rec.stop}>
                Stop
              </button>
            )}
            {rec.status === 'stopped' && (
              <button type="button" className="button default" onClick={saveTake}>
                Save take
              </button>
            )}
            {rec.status !== 'idle' && (
              <button type="button" className="button" onClick={startOver}>
                Start over
              </button>
            )}
          </div>

          {rec.url && rec.status === 'stopped' && <AudioPlayer src={rec.url} durationSec={rec.elapsedMs / 1000} label="This take" />}
          {rec.error && (
            <p className="inline-alert" role="alert">
              <Icon name="caution" />
              {rec.error}
            </p>
          )}
        </Window>

        <Window
          title="Takes"
          className="takes-window"
          footer={
            <>
              <button type="button" className="button" onClick={() => uploadRef.current?.click()} disabled={!score || busy}>
                Upload…
              </button>
              <button type="button" className="button" onClick={() => selected && download(selected)} disabled={!selected}>
                Download
              </button>
              <button type="button" className="button" onClick={() => selected && takes.remove(selected)} disabled={!selected || busy}>
                Delete
              </button>
              <span className="footer-gap" />
              <button type="button" className="button default" onClick={() => selected && onEvaluate(selected)} disabled={!selected || busy}>
                Evaluate
              </button>
            </>
          }
        >
          <div className="list well" role="listbox" aria-label="Saved takes">
            <div className="list-head" aria-hidden="true">
              <span>Name</span>
              <span>Length</span>
              <span>Saved</span>
            </div>
            {takes.takes.length === 0 ? (
              <p className="list-empty">No takes yet. Record one and press Save take, or upload a recording.</p>
            ) : (
              takes.takes.map((t) => (
                <div
                  key={t.id}
                  role="option"
                  aria-selected={t.id === selectedId}
                  tabIndex={0}
                  className={`list-row${t.id === selectedId ? ' selected' : ''}`}
                  title={`${t.scoreName}: double-click to evaluate`}
                  onClick={() => setSelectedId(t.id)}
                  onDoubleClick={() => !busy && onEvaluate(t)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !busy) onEvaluate(t)
                    if (e.key === ' ') {
                      e.preventDefault()
                      setSelectedId(t.id)
                    }
                  }}
                >
                  <span className="list-name">
                    <Icon name="note" />
                    {t.name}
                  </span>
                  <span>{shortLength(t.durationMs)}</span>
                  <span>{t.savedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
                </div>
              ))
            )}
          </div>
          {selected && <AudioPlayer key={selected.id} src={selected.url} durationSec={selected.durationMs / 1000} label={selected.name} />}
          {uploadError && (
            <p className="inline-alert" role="alert">
              <Icon name="caution" />
              {uploadError}
            </p>
          )}
        </Window>
      </main>

      {/* Count-in: the beats as a dialog over the desktop; then a short "Sing!" so the start is unmistakable. */}
      {rec.status === 'countin' && countIn && (
        <div className="modal-layer" aria-live="assertive">
          <DialogBox icon={<Icon name="note" size={2} />} role="dialog">
            <p>
              <b>Get ready</b> · ♩ = {tempo}
            </p>
            <div className="countin">
              {/* Empty until the first click: anything shown before "1" reads as an extra beat. */}
              <span key={rec.countInBeat} className="countin-beat">
                {rec.countInBeat || ''}
              </span>
              <span className="countin-dots">
                {Array.from({ length: countIn.beats }, (_, i) => (
                  <i key={i} className={i < rec.countInBeat ? 'on' : ''} />
                ))}
              </span>
            </div>
          </DialogBox>
        </div>
      )}
      {rec.status === 'recording' && rec.elapsedMs < 1200 && (
        <div className="modal-layer" aria-live="assertive">
          <DialogBox icon={<span className="lamp recording big" aria-hidden="true" />} role="dialog">
            <p className="sing-now">Sing!</p>
            <p>Recording. Press Stop when you're done.</p>
          </DialogBox>
        </div>
      )}
    </div>
  )
}
