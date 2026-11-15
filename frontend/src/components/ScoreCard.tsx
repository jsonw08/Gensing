import type { Results } from '../lib/api'
import { STATUS_COLOR } from '../lib/colorScore'
import { Progress } from './desktop/Window'

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

// Pitch result per written note: one meter segment each (colors match the score's legend).
const PITCH: { key: string; label: string; color: string }[] = [
  { key: 'in_tune', label: 'in tune', color: STATUS_COLOR.in_tune },
  { key: 'out_of_tune', label: 'out of tune', color: STATUS_COLOR.out_of_tune },
  { key: 'wrong_note', label: 'wrong note', color: STATUS_COLOR.wrong_note },
  { key: 'skipped', label: 'skipped', color: STATUS_COLOR.skipped },
]

function octaveNote(shift: number): string | null {
  if (shift === 0) return null
  const n = Math.abs(shift) / 12
  return `Sung ${n === 1 ? 'an octave' : `${n} octaves`} ${shift < 0 ? 'lower' : 'higher'} than written.`
}

/** The Results window's contents: total, the four parts, the notes meter and the grading settings. */
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
  const pitch = PITCH.filter((p) => c(p.key) > 0)
  const octave = octaveNote(meta.octave_shift)
  const uncertain = c('uncertain')

  return (
    <>
      <div className="total" aria-busy={busy}>
        <span className={`total-number${busy ? ' busy' : ''}`}>{score.total}</span>
        <span className="total-caption">
          <span>out of 100</span>
          <span>
            {c('in_tune')} of {c('notes')} notes in tune
          </span>
        </span>
      </div>
      {busy && <Progress label="Re-scoring" />}

      <ul className="score-rows">
        {PARTS.map((p) => (
          <li key={p.key} title={p.hint}>
            <span>{p.label}</span>
            <b>{score[p.key]}</b>
          </li>
        ))}
      </ul>

      <div>
        <div className="notes-meter well" role="img" aria-label={pitch.map((p) => `${c(p.key)} ${p.label}`).join(', ')}>
          {pitch.map((p) => (
            <span key={p.key} title={`${c(p.key)} ${p.label}`} style={{ flexGrow: c(p.key), background: p.color }} />
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
        <fieldset className={`radio-group${busy ? ' busy' : ''}`} disabled={busy}>
          <legend>Grading</legend>
          <RadioRow
            label="Timing"
            name="timing"
            options={MODES}
            value={grading.mode}
            onChange={(mode) => onGradingChange({ ...grading, mode })}
          />
          <RadioRow
            label="Level"
            name="level"
            options={PRESETS}
            value={grading.preset}
            onChange={(preset) => onGradingChange({ ...grading, preset })}
          />
        </fieldset>
      )}
    </>
  )
}

function RadioRow<T extends string>({
  label,
  name,
  options,
  value,
  onChange,
}: {
  label: string
  name: string
  options: { value: T; label: string; hint: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="grading-row" role="radiogroup" aria-label={label}>
      <span className="grading-label">{label}</span>
      <div className="radio-row">
        {options.map((o) => (
          <label key={o.value} className="radio" title={o.hint}>
            <input type="radio" name={name} checked={o.value === value} onChange={() => onChange(o.value)} />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
