import type { Results } from '../lib/api'
import { STATUS_COLOR } from '../lib/colorScore'

/** How the take is graded (sent to /analyze; changing it re-analyzes). */
export type Grading = { mode: 'free' | 'strict'; preset: 'default' | 'beginner' | 'advanced' }

const MODES: { value: Grading['mode']; label: string; hint: string }[] = [
  { value: 'free', label: 'Free tempo', hint: 'Timing judged against your own pulse' },
  { value: 'strict', label: 'Strict', hint: "Timing judged against the score's tempo" },
]
const PRESETS: { value: Grading['preset']; label: string; hint: string }[] = [
  { value: 'beginner', label: 'Beginner', hint: 'In tune within 35 cents, on time within 1/4 beat' },
  { value: 'default', label: 'Standard', hint: 'In tune within 25 cents, on time within 1/8 beat' },
  { value: 'advanced', label: 'Advanced', hint: 'In tune within 15 cents, on time within 1/16 beat' },
]

// The overall score (results.score) and what it's made of: the demo's "overall score" must-have.
// Weights and rules: docs/DECISIONS.md 4.5 (stage 5 computes everything; nothing is calculated here).

const PARTS: { key: 'pitch' | 'intonation' | 'rhythm' | 'completeness'; label: string; hint: string }[] = [
  { key: 'pitch', label: 'Pitch', hint: 'Notes sung on the right pitch (50% of the total)' },
  { key: 'intonation', label: 'Intonation', hint: 'How close to the center of the note, right notes only (25%)' },
  { key: 'rhythm', label: 'Rhythm', hint: 'Notes that started on time (15%)' },
  { key: 'completeness', label: 'Completeness', hint: 'Nothing skipped, nothing extra (10%)' },
]

// Pitch result per written note: one bar segment each (colors explained by the legend over the score;
// the count shows on hover). Timing and extras are marked on the score itself.
const PITCH: { key: string; label: string; color: string }[] = [
  { key: 'in_tune', label: 'in tune', color: STATUS_COLOR.in_tune },
  { key: 'out_of_tune', label: 'out of tune', color: STATUS_COLOR.out_of_tune },
  { key: 'wrong_note', label: 'wrong note', color: STATUS_COLOR.wrong_note },
  { key: 'skipped', label: 'skipped', color: STATUS_COLOR.skipped },
]

function verdict(total: number): { word: string; color: string } {
  if (total >= 90) return { word: 'Excellent', color: STATUS_COLOR.in_tune }
  if (total >= 75) return { word: 'Good', color: STATUS_COLOR.in_tune }
  if (total >= 55) return { word: 'Getting there', color: STATUS_COLOR.out_of_tune }
  return { word: 'Keep practicing', color: STATUS_COLOR.wrong_note }
}

function octaveNote(shift: number): string | null {
  if (shift === 0) return null
  const n = Math.abs(shift) / 12
  return `Sung ${n === 1 ? 'an octave' : `${n} octaves`} ${shift < 0 ? 'lower' : 'higher'} than written.`
}

export function ScoreCard({
  results,
  grading,
  onGradingChange,
  busy = false,
}: {
  results: Results
  grading?: Grading
  onGradingChange?: (g: Grading) => void
  busy?: boolean
}) {
  const { score, counts, meta } = results
  const c = (k: string) => counts[k] ?? 0
  const v = verdict(score.total)
  const pitch = PITCH.filter((p) => c(p.key) > 0)
  const octave = octaveNote(meta.octave_shift)
  const uncertain = c('uncertain')

  return (
    <section className={`score-card${busy ? ' busy' : ''}`} aria-label="Score" aria-busy={busy}>
      <header className="score-head">
        <div>
          <span className="score-eyebrow">Overall</span>
          <span className="score-total">
            {score.total}
            <small>/100</small>
          </span>
        </div>
        {busy ? (
          <span className="score-pill updating">Re-scoring…</span>
        ) : (
          <span className="score-pill" style={{ color: v.color, background: `color-mix(in srgb, ${v.color} 12%, white)` }}>
            {v.word}
          </span>
        )}
      </header>

      <ul className="score-parts">
        {PARTS.map((p) => (
          <li key={p.key} title={p.hint}>
            <span className="score-eyebrow">{p.label}</span>
            <span className="score-part-value">{score[p.key]}</span>
            <span className="score-bar" aria-hidden="true">
              <span style={{ width: `${score[p.key]}%` }} />
            </span>
          </li>
        ))}
      </ul>

      <div className="score-notes-block">
        <div className="score-row">
          <span className="score-eyebrow">Notes</span>
          <span className="score-row-value">
            {c('in_tune')} of {c('notes')} in tune
          </span>
        </div>
        <div className="score-split">
          {pitch.map((p) => (
            <span
              key={p.key}
              title={`${c(p.key)} ${p.label}${p.key === 'wrong_note' && c(p.key) > 1 ? 's' : ''}`}
              style={{ flexGrow: c(p.key), background: p.color }}
            />
          ))}
        </div>
        {octave && <p className="score-meta">{octave}</p>}
        {uncertain > 0 && (
          <p className="score-meta">
            {uncertain} note{uncertain === 1 ? ' was' : 's were'} hard to hear (not scored).
          </p>
        )}
      </div>

      {grading && onGradingChange && (
        <div className="score-settings">
          <div className="score-row">
            <span className="score-eyebrow">Timing</span>
            <Segmented options={MODES} value={grading.mode} disabled={busy} onChange={(mode) => onGradingChange({ ...grading, mode })} />
          </div>
          <div className="score-row">
            <span className="score-eyebrow">Level</span>
            <Segmented options={PRESETS} value={grading.preset} disabled={busy} onChange={(preset) => onGradingChange({ ...grading, preset })} />
          </div>
        </div>
      )}
    </section>
  )
}

function Segmented<T extends string>({
  options,
  value,
  disabled,
  onChange,
}: {
  options: { value: T; label: string; hint: string }[]
  value: T
  disabled: boolean
  onChange: (v: T) => void
}) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          className={o.value === value ? 'on' : ''}
          title={o.hint}
          disabled={disabled}
          onClick={() => o.value !== value && onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
