// Count-in clicks with the Web Audio API: sample-accurate timing, no audio files needed.
// The first click of the bar is higher (accented). Headphones keep the clicks out of the recording.
//
// One AudioContext for the whole session, kept running: opening a new one per take loses the first
// few hundred ms while the output device wakes up (worst on Bluetooth headphones), which swallowed a
// varying number of clicks.

let shared: AudioContext | null = null

/** The session's AudioContext, resumed. Call it from a click handler (browsers need a user gesture). */
export function audioContext(): AudioContext {
  if (!shared || shared.state === 'closed') shared = new AudioContext()
  if (shared.state === 'suspended') shared.resume().catch(() => {})
  return shared
}

/** Keep the output device awake: a silent sound now, so the first real click isn't cut off. */
export function warmUp(ctx: AudioContext) {
  const buffer = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * 0.05), ctx.sampleRate)
  const src = ctx.createBufferSource()
  src.buffer = buffer
  src.connect(ctx.destination)
  src.start()
}

/** The audio-clock time currently coming out of the speakers (currentTime minus output latency). */
export function heardAudioTime(ctx: AudioContext): number {
  const ts = ctx.getOutputTimestamp?.()
  if (ts?.contextTime !== undefined && ts.contextTime > 0) return ts.contextTime
  return ctx.currentTime - (ctx.outputLatency || ctx.baseLatency || 0)
}

/** performance.now() at which audio-clock time `t` is heard. */
export function audioTimeToPerf(ctx: AudioContext, t: number): number {
  const ts = ctx.getOutputTimestamp?.()
  if (ts?.contextTime !== undefined && ts.performanceTime !== undefined && ts.contextTime > 0) {
    return ts.performanceTime + (t - ts.contextTime) * 1000
  }
  return performance.now() + (t - ctx.currentTime + (ctx.outputLatency || ctx.baseLatency || 0)) * 1000
}

/** Schedule `count` clicks; returns a function that silences any not yet played. */
export function scheduleClicks(ctx: AudioContext, startAt: number, count: number, intervalSec: number): () => void {
  const bus = ctx.createGain() // all clicks of this count-in go through one node, so they can be cancelled
  bus.connect(ctx.destination)
  for (let i = 0; i < count; i++) {
    const t = startAt + i * intervalSec
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = i === 0 ? 1760 : 1175 // accented downbeat
    // Louder and a little longer than a bare blip, so it's easy to hear on laptop speakers.
    gain.gain.setValueAtTime(0.0001, t)
    gain.gain.exponentialRampToValueAtTime(0.9, t + 0.002)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.11)
    osc.connect(gain).connect(bus)
    osc.start(t)
    osc.stop(t + 0.12)
  }
  return () => bus.disconnect()
}
