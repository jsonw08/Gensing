// Length of an audio file in ms, read from its metadata. 0 if the browser can't tell
// (some WebM files report Infinity until fully played).
export function audioDurationMs(blob: Blob): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob)
    const audio = new Audio()
    const done = (ms: number) => {
      URL.revokeObjectURL(url)
      resolve(ms)
    }
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => done(Number.isFinite(audio.duration) ? audio.duration * 1000 : 0)
    audio.onerror = () => done(0)
    audio.src = url
  })
}

/** True if the browser can decode this file (so it can be played and, later, converted to WAV). */
export function isPlayableAudio(file: File): Promise<boolean> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const audio = new Audio()
    const done = (ok: boolean) => {
      URL.revokeObjectURL(url)
      resolve(ok)
    }
    audio.oncanplay = () => done(true)
    audio.onloadedmetadata = () => done(true)
    audio.onerror = () => done(false)
    audio.src = url
  })
}

const EXTENSIONS: Record<string, string> = {
  'audio/webm': 'webm',
  'audio/ogg': 'ogg',
  'audio/mp4': 'm4a',
  'audio/x-m4a': 'm4a',
  'audio/mpeg': 'mp3',
  'audio/wav': 'wav',
  'audio/x-wav': 'wav',
  'audio/wave': 'wav',
}

/** Save a recording to the user's Downloads: an uploaded file keeps its own name; a recording is named
 *  "<score> - <take>.<ext>", with the extension from what the browser recorded (WebM in Chrome, MP4 in Safari). */
export function downloadRecording(blob: Blob, url: string, takeName: string, scoreName: string) {
  const ownName = blob instanceof File ? blob.name : null
  const ext = EXTENSIONS[blob.type.split(';')[0].trim()] ?? 'webm'
  const score = scoreName.replace(/\.[^.]+$/, '')
  const a = document.createElement('a')
  a.href = url
  a.download = ownName ?? `${score} - ${takeName}.${ext}`
  document.body.append(a)
  a.click()
  a.remove()
}
