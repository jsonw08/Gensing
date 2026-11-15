// The starting note: the score's first sung pitch, played as a held tone so the singer can find it
// before the count-in. Same note the backend grades first (docs/DECISIONS.md section 3): first part,
// voice 1, grace notes and rests skipped, top note of a chord.

export type StartNote = { name: string; midi: number; frequency: number }

const STEP_SEMITONES: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
const NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

function midiOf(note: Element): number | null {
  const step = note.querySelector('pitch > step')?.textContent?.trim() ?? ''
  const octave = Number(note.querySelector('pitch > octave')?.textContent)
  const alter = Number(note.querySelector('pitch > alter')?.textContent ?? 0) || 0
  if (!(step in STEP_SEMITONES) || !Number.isFinite(octave)) return null
  return Math.round((octave + 1) * 12 + STEP_SEMITONES[step] + alter)
}

/** The first sung note of the score, or null if it has none. */
export function readStartNote(xml: string): StartNote | null {
  const doc = new DOMParser().parseFromString(xml, 'application/xml')
  const part = doc.querySelector('part')
  if (!part) return null
  let midi: number | null = null
  for (const note of part.querySelectorAll('note')) {
    const isChordTone = !!note.querySelector('chord')
    if (midi !== null && !isChordTone) break // the first note (and its chord tones) is done
    if (note.querySelector('grace, rest, cue')) continue
    const voice = note.querySelector('voice')?.textContent?.trim()
    if (voice && voice !== '1') continue
    const m = midiOf(note)
    if (m !== null) midi = midi === null ? m : Math.max(midi, m) // top note of a chord
  }
  if (midi === null) return null
  return {
    name: `${NAMES[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`,
    midi,
    frequency: 440 * 2 ** ((midi - 69) / 12),
  }
}

// Recorded piano: Salamander Grand Piano by Alexander Holm (CC-BY 3.0), the copies Tone.js hosts.
// One recording every 3 semitones from C2 to C6 in public/piano/ (served locally, works offline);
// a note is played from the nearest recording, retuned by at most 1.5 semitones, which still sounds natural.
const SAMPLE_LOW = 36 // C2
const SAMPLE_HIGH = 84 // C6
const SAMPLE_PITCHES = ['C', 'Ds', 'Fs', 'A'] // pitch classes 0, 3, 6, 9

function nearestSample(midi: number): { file: string; midi: number } {
  const m = Math.min(SAMPLE_HIGH, Math.max(SAMPLE_LOW, Math.round(midi / 3) * 3))
  return { file: `${SAMPLE_PITCHES[(m % 12) / 3]}${Math.floor(m / 12) - 1}`, midi: m }
}

const sampleBytes = new Map<string, Promise<ArrayBuffer>>()
const sampleBuffers = new Map<string, Promise<AudioBuffer>>()

function fetchSample(file: string): Promise<ArrayBuffer> {
  let bytes = sampleBytes.get(file)
  if (!bytes) {
    bytes = fetch(`${import.meta.env.BASE_URL}piano/${file}.mp3`).then((r) => {
      if (!r.ok) throw new Error(`piano sample ${file}: HTTP ${r.status}`)
      return r.arrayBuffer()
    })
    bytes.catch(() => sampleBytes.delete(file)) // try again next time
    sampleBytes.set(file, bytes)
  }
  return bytes
}

/** Download the recording for this note ahead of time, so the first press plays at once. */
export function preloadNote(midi: number) {
  fetchSample(nearestSample(midi).file).catch(() => {})
}

function sampleBuffer(ctx: BaseAudioContext, file: string): Promise<AudioBuffer> {
  let buffer = sampleBuffers.get(file)
  if (!buffer) {
    // decodeAudioData takes ownership of its input, so decode a copy (the bytes stay cached)
    buffer = fetchSample(file).then((b) => ctx.decodeAudioData(b.slice(0)))
    buffer.catch(() => sampleBuffers.delete(file))
    sampleBuffers.set(file, buffer) // an AudioBuffer works in any AudioContext
  }
  return buffer
}

/** Play a piano note now (MIDI number). Falls back to the synth if the recording can't be loaded.
 *  Resolves to a function that stops it early. */
export async function playNote(ctx: AudioContext, midi: number, durationSec = 2): Promise<() => void> {
  try {
    const sample = nearestSample(midi)
    const buffer = await sampleBuffer(ctx, sample.file)
    const t = ctx.currentTime + 0.02 // audio-clock times are absolute: always offset from currentTime
    const end = t + durationSec
    const src = ctx.createBufferSource()
    src.buffer = buffer
    src.playbackRate.value = 2 ** ((midi - sample.midi) / 12) // retune to the exact note
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(1, t)
    gain.gain.setValueAtTime(1, end - 0.3)
    gain.gain.linearRampToValueAtTime(0, end) // damper: fade out instead of ringing for seconds
    src.connect(gain).connect(ctx.destination)
    src.start(t)
    src.stop(end + 0.05)
    return () => {
      try {
        src.stop()
      } catch {
        /* already stopped */
      }
    }
  } catch (err) {
    console.warn('[piano] recording unavailable, using the synth', err)
    return playSynthNote(ctx, 440 * 2 ** ((midi - 69) / 12), durationSec)
  }
}

// Fallback: a piano-like tone built from sine waves (no files). What makes it sound like a piano:
//   - harmonics that get quieter going up, and slightly sharp (stiff strings: "inharmonicity")
//   - a hammer strike: instant attack, then every harmonic decays, the high ones fastest,
//     so the sound starts bright and mellows; low notes ring longer than high ones
//   - two strings per note, a fraction of a cent apart, which gives the slow shimmer
//   - a short, soft thump of filtered noise at the start (the hammer hitting the string)
const PARTIALS = 10
const INHARMONICITY = 0.0004 // B in f_n = n·f·sqrt(1 + B·n²)
const DETUNE_CENTS = 0.8 // second string of each note

/** Play the synth note now. Returns a function that stops it early. */
function playSynthNote(ctx: AudioContext, frequency: number, durationSec = 2): () => void {
  const t = ctx.currentTime + 0.02 // audio-clock times are absolute: always offset from currentTime
  const end = t + durationSec
  const nyquist = ctx.sampleRate / 2

  // Master volume, with a short release at the end (a damper coming down).
  const master = ctx.createGain()
  master.gain.setValueAtTime(0.3, t)
  master.gain.setValueAtTime(0.3, end - 0.25)
  master.gain.linearRampToValueAtTime(0, end)
  master.connect(ctx.destination)

  // Low notes sustain longer: ~1.6 s decay constant at middle C, shorter going up.
  const baseTau = Math.min(3, Math.max(0.4, 1.6 * (261.6 / frequency) ** 0.5))
  const oscs: OscillatorNode[] = []

  for (let n = 1; n <= PARTIALS; n++) {
    const f = n * frequency * Math.sqrt(1 + INHARMONICITY * n * n)
    if (f > nyquist * 0.9) break
    const amp = 0.6 / n ** 1.3 // quieter going up
    const tau = baseTau / n ** 0.8 // high harmonics die away faster
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0, t)
    gain.gain.linearRampToValueAtTime(amp, t + 0.004) // hammer: near-instant attack
    gain.gain.setTargetAtTime(0, t + 0.004, tau) // then a natural exponential decay
    gain.connect(master)
    for (const cents of n <= 3 ? [0, DETUNE_CENTS] : [0]) {
      const osc = ctx.createOscillator()
      osc.frequency.value = f * 2 ** (cents / 1200)
      osc.connect(gain)
      osc.start(t)
      osc.stop(end + 0.05)
      oscs.push(osc)
    }
  }

  // Hammer thump: 40 ms of noise through a low-pass filter, fading fast.
  const noise = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * 0.04), ctx.sampleRate)
  const data = noise.getChannelData(0)
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
  const thump = ctx.createBufferSource()
  thump.buffer = noise
  const filter = ctx.createBiquadFilter()
  filter.type = 'lowpass'
  filter.frequency.value = Math.min(nyquist * 0.9, frequency * 6)
  const thumpGain = ctx.createGain()
  thumpGain.gain.setValueAtTime(0.12, t)
  thumpGain.gain.setTargetAtTime(0, t, 0.01)
  thump.connect(filter).connect(thumpGain).connect(master)
  thump.start(t)

  return () => {
    for (const osc of oscs) {
      try {
        osc.stop()
      } catch {
        /* already stopped */
      }
    }
  }
}
