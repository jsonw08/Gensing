// Any recording or uploaded audio file -> 16-bit mono WAV for /analyze (docs/DECISIONS.md section 5: the
// backend only reads WAV; browsers record WebM (Chrome) or MP4 (Safari), which librosa can't read without
// ffmpeg). The browser's own decoder does the work, so any format it can play converts.
//
// 16 kHz: stage 2 resamples to 16 kHz anyway, so nothing is lost, and the upload stays small
// (32 KB per second: 30 s ~ 1 MB). The timeline is kept as is, so countin_end_sec still points at beat 1.

export const WAV_SAMPLE_RATE = 16000

/** Decode `audio` (any format the browser can play), mix to mono, resample to 16 kHz, encode as WAV. */
export async function toWav(audio: Blob): Promise<Blob> {
  // decodeAudioData resamples to the context's rate; an OfflineAudioContext needs no user gesture.
  const ctx = new OfflineAudioContext(1, 1, WAV_SAMPLE_RATE)
  let decoded: AudioBuffer
  try {
    decoded = await ctx.decodeAudioData(await audio.arrayBuffer())
  } catch {
    throw new Error("This recording couldn't be decoded by the browser. Try a WAV, MP3 or M4A file.")
  }
  return new Blob([encodeWav(mixToMono(decoded), decoded.sampleRate)], { type: 'audio/wav' })
}

/** Average of all channels. */
export function mixToMono(buffer: Pick<AudioBuffer, 'numberOfChannels' | 'length' | 'getChannelData'>): Float32Array {
  if (buffer.numberOfChannels === 1) return buffer.getChannelData(0)
  const out = new Float32Array(buffer.length)
  for (let c = 0; c < buffer.numberOfChannels; c++) {
    const data = buffer.getChannelData(c)
    for (let i = 0; i < out.length; i++) out[i] += data[i] / buffer.numberOfChannels
  }
  return out
}

/** 16-bit PCM mono WAV: a 44-byte RIFF header, then the samples (clipped to -1..1). */
export function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const bytes = new ArrayBuffer(44 + samples.length * 2)
  const v = new DataView(bytes)
  const text = (at: number, s: string) => [...s].forEach((ch, i) => v.setUint8(at + i, ch.charCodeAt(0)))
  text(0, 'RIFF')
  v.setUint32(4, 36 + samples.length * 2, true) // rest of the file
  text(8, 'WAVE')
  text(12, 'fmt ')
  v.setUint32(16, 16, true) // fmt chunk size
  v.setUint16(20, 1, true) // PCM
  v.setUint16(22, 1, true) // mono
  v.setUint32(24, sampleRate, true)
  v.setUint32(28, sampleRate * 2, true) // bytes per second
  v.setUint16(32, 2, true) // bytes per frame
  v.setUint16(34, 16, true) // bits per sample
  text(36, 'data')
  v.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return bytes
}
