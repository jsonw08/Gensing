import { useCallback, useEffect, useRef, useState } from 'react'

export type RecorderStatus = 'idle' | 'recording' | 'stopped'

// Microphone recorder with stop / restart, built on MediaRecorder.
// Output is whatever the browser records (WebM/MP4); WAV conversion happens before upload (later step).
export function useRecorder() {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [url, setUrl] = useState<string | null>(null) // object URL of `blob`, for playback
  const [error, setError] = useState<string | null>(null)

  const recRef = useRef<MediaRecorder | null>(null)
  const urlRef = useRef<string | null>(null)
  const startedAtRef = useRef(0) // performance.now() when recording began

  // Tick the timer only while actually recording.
  useEffect(() => {
    if (status !== 'recording') return
    const id = setInterval(() => {
      setElapsedMs(performance.now() - startedAtRef.current)
    }, 100)
    return () => clearInterval(id)
  }, [status])

  // Replace the current take (or clear it with null), freeing the old object URL.
  const setTake = useCallback((b: Blob | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    urlRef.current = b ? URL.createObjectURL(b) : null
    setBlob(b)
    setUrl(urlRef.current)
  }, [])

  // Stop the current recorder without keeping its audio.
  const discard = useCallback(() => {
    const rec = recRef.current
    recRef.current = null // its onstop sees it's no longer current and drops the data
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [])

  const start = useCallback(async () => {
    discard()
    setError(null)
    setTake(null)
    setElapsedMs(0)
    try {
      // Browser voice processing distorts pitch and dynamics; turn it off for singing.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      })
      const rec = new MediaRecorder(stream)
      const chunks: Blob[] = []
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop()) // release the mic
        if (recRef.current !== rec) return // discarded (restart / reset / unmount)
        setTake(new Blob(chunks, { type: rec.mimeType }))
        setStatus('stopped')
      }
      recRef.current = rec
      rec.start()
      startedAtRef.current = performance.now()
      setStatus('recording')
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Microphone access was denied. Allow it in your browser settings and try again.'
          : `Could not start recording: ${String(err)}`,
      )
      setStatus('idle')
    }
  }, [discard, setTake])

  const stop = useCallback(() => {
    const rec = recRef.current
    if (!rec || rec.state === 'inactive') return
    setElapsedMs(performance.now() - startedAtRef.current)
    rec.stop() // onstop sets the blob and status
  }, [])

  // Throw away the take and record a new one straight away.
  const restart = useCallback(() => start(), [start])

  // Throw away the take and go back to the idle state.
  const reset = useCallback(() => {
    discard()
    setTake(null)
    setElapsedMs(0)
    setStatus('idle')
  }, [discard, setTake])

  // On unmount: release the mic and free the playback URL.
  useEffect(
    () => () => {
      discard()
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    },
    [discard],
  )

  return { status, elapsedMs, blob, url, error, start, stop, restart, reset }
}
