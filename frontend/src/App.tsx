import { useEffect, useState } from 'react'
import { ScoreView } from './components/ScoreView'
import { analyze, feedback, health } from './lib/api'

// Bare-bones dev page: proves frontend <-> backend <-> OSMD are wired up.
// Real screens (Setup, Record, Results) come later.
export default function App() {
  const [backendUp, setBackendUp] = useState<boolean | null>(null)
  const [scoreFile, setScoreFile] = useState<File | null>(null)
  const [scoreXml, setScoreXml] = useState<string | null>(null)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [output, setOutput] = useState<string>('')

  useEffect(() => {
    health().then(setBackendUp)
  }, [])

  async function onScoreChange(file: File | undefined) {
    if (!file) return
    setScoreFile(file)
    setScoreXml(await file.text())
  }

  async function runAnalyze() {
    if (!scoreFile || !audioFile) return
    try {
      const analysis = await analyze(scoreFile, audioFile, { mode: 'strict' })
      setOutput(JSON.stringify(analysis.results, null, 2))
      const fb = await feedback(analysis.results)
      setOutput((prev) => prev + '\n\n' + JSON.stringify(fb, null, 2))
    } catch (err) {
      setOutput(String(err))
    }
  }

  return (
    <main>
      <h1>Gensing</h1>
      <p>
        Backend:{' '}
        {backendUp === null ? 'checking…' : backendUp ? 'connected' : 'not reachable (is uvicorn running?)'}
      </p>

      <section className="controls">
        <label>
          MusicXML{' '}
          <input
            type="file"
            accept=".musicxml,.xml,.mxl"
            onChange={(e) => onScoreChange(e.target.files?.[0])}
          />
        </label>
        <label>
          Recording{' '}
          <input type="file" accept="audio/*" onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)} />
        </label>
        <button onClick={runAnalyze} disabled={!scoreFile || !audioFile}>
          Analyze
        </button>
      </section>

      {scoreXml && <ScoreView xml={scoreXml} />}
      {output && <pre className="output">{output}</pre>}
    </main>
  )
}
