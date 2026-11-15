import { useCallback, useEffect, useRef, useState } from 'react'
import { audioContext, audioTimeToPerf, heardAudioTime, scheduleClicks, warmUp } from '../lib/metronome'

export type RecorderStatus = 'idle' | 'countin' | 'recording' | 'stopped'

export type CountIn = { beats: number; intervalSec: number }

const MIC_SETTLE_MS = 400 // after first opening the mic, before the first click
const CLICK_LEAD_SEC = 0.25 // schedule the first click this far ahead

// Microphone recorder with a count-in, stop and restart, built on MediaRecorder.
//
// The mic starts BEFORE the count-in, so the recording begins with the clicks and `countinEndSec` says
// where beat 1 is in it (sent to /analyze as countin_end_sec; stage 5 also removes the remaining
// latency offset). Output is whatever the browser records (WebM/MP4); WAV conversion comes later.
//
// The count-in runs on the AUDIO clock: the on-screen beat and the switch to "recording" are read from
// the same clock the clicks are played on, and scheduled clicks are never cut off at beat 1. (Driving
// them with setTimeout let the screen run ahead whenever the audio clock stalled, and clicks that were
// running late got silenced: a different number of audible beats per take.)
//
// The mic stream stays open between takes while the page is mounted, so the audio system isn't
// reconfigured on every take.
export function useRecorder() {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsedMs, setElapsedMs] = useState(0) // time since beat 1
  const [countInBeat, setCountInBeat] = useState(0) // 1..beats during the count-in
  const [countinEndSec, setCountinEndSec] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [url, setUrl] = useState<string | null>(null) // object URL of `blob`, for playback
  const [error, setError] = useState<string | null>(null)

  const recRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const urlRef = useRef<string | null>(null)
  const beatOneAtRef = useRef(0) // performance.now() at beat 1
  const rafRef = useRef(0)
  const cancelClicksRef = useRef<(() => void) | null>(null)

  // Tick the timer only while actually recording.
  useEffect(() => {
    if (status !== 'recording') return
    const id = setInterval(() => setElapsedMs(performance.now() - beatOneAtRef.current), 100)
    return () => clearInterval(id)
  }, [status])

  // Replace the current take (or clear it with null), freeing the old object URL.
  const setTake = useCallback((b: Blob | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    urlRef.current = b ? URL.createObjectURL(b) : null
    setBlob(b)
    setUrl(urlRef.current)
  }, [])

  // Abandon a count-in: stop watching the clock and silence clicks not yet played.
  const stopCountIn = useCallback(() => {
    cancelAnimationFrame(rafRef.current)
    cancelClicksRef.current?.()
    cancelClicksRef.current = null
  }, [])

  // Stop the current recorder without keeping its audio.
  const discard = useCallback(() => {
    stopCountIn()
    const rec = recRef.current
    recRef.current = null // its onstop sees it's no longer current and drops the data
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [stopCountIn])

  // An open mic stream, reused across takes; `fresh` = it was just opened.
  const openMic = useCallback(async () => {
    const live = streamRef.current?.getAudioTracks().some((t) => t.readyState === 'live')
    if (live && streamRef.current) return { stream: streamRef.current, fresh: false }
    // Browser voice processing distorts pitch and dynamics; turn it off for singing.
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    })
    streamRef.current = stream
    return { stream, fresh: true }
  }, [])

  const start = useCallback(
    async (countIn?: CountIn) => {
      discard()
      // Grab the audio output now, while still inside the click (browsers only allow audio after a user
      // gesture), and wake it up so it's ready by the time the clicks play.
      const ctx = countIn && countIn.beats > 0 ? audioContext() : null
      if (ctx) warmUp(ctx)
      setError(null)
      setTake(null)
      setElapsedMs(0)
      setCountInBeat(0)
      beatOneAtRef.current = 0
      try {
        const { stream, fresh } = await openMic()
        const rec = new MediaRecorder(stream)
        const chunks: Blob[] = []
        rec.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data)
        }
        rec.onstop = () => {
          if (recRef.current !== rec) return // discarded (restart / reset / unmount)
          setTake(new Blob(chunks, { type: rec.mimeType }))
          setStatus('stopped')
        }
        recRef.current = rec
        rec.start()
        const recStartedAt = performance.now()

        const beginSinging = (atPerf: number) => {
          beatOneAtRef.current = atPerf
          setCountinEndSec(Math.max(0, (atPerf - recStartedAt) / 1000))
          setCountInBeat(0)
          setStatus('recording')
        }

        if (!ctx || !countIn) {
          beginSinging(recStartedAt)
          return
        }

        setStatus('countin')
        if (fresh) {
          // A just-opened mic can briefly disturb audio output; let it settle before the first click.
          await new Promise((r) => setTimeout(r, MIC_SETTLE_MS))
          if (recRef.current !== rec) return // stopped or restarted meanwhile
        }
        await ctx.resume()

        // Schedule one bar of clicks, then follow the audio clock (what's being heard) frame by frame.
        const firstClick = ctx.currentTime + CLICK_LEAD_SEC
        const beatOne = firstClick + countIn.beats * countIn.intervalSec
        cancelClicksRef.current = scheduleClicks(ctx, firstClick, countIn.beats, countIn.intervalSec)
        const follow = () => {
          if (recRef.current !== rec) return
          const now = heardAudioTime(ctx)
          if (now >= beatOne) {
            cancelClicksRef.current = null // all clicks have played; nothing to cancel
            beginSinging(audioTimeToPerf(ctx, beatOne))
            return
          }
          setCountInBeat(now >= firstClick ? Math.floor((now - firstClick) / countIn.intervalSec) + 1 : 0)
          rafRef.current = requestAnimationFrame(follow)
        }
        rafRef.current = requestAnimationFrame(follow)
      } catch (err) {
        discard()
        setError(
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Microphone access was denied. Allow it in your browser settings and try again.'
            : `Could not start recording: ${String(err)}`,
        )
        setStatus('idle')
      }
    },
    [discard, openMic, setTake],
  )

  const stop = useCallback(() => {
    const rec = recRef.current
    if (!rec || rec.state === 'inactive') return
    stopCountIn()
    if (beatOneAtRef.current) setElapsedMs(Math.max(0, performance.now() - beatOneAtRef.current))
    rec.stop() // onstop sets the blob and status
  }, [stopCountIn])

  // Throw away the take and go back to the idle state.
  const reset = useCallback(() => {
    discard()
    setTake(null)
    setElapsedMs(0)
    setCountInBeat(0)
    setStatus('idle')
  }, [discard, setTake])

  // On unmount: stop recording, release the mic and free the playback URL.
  useEffect(
    () => () => {
      discard()
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    },
    [discard],
  )

  // restart = start again (throws the current take away); it takes the same count-in argument.
  return { status, elapsedMs, countInBeat, countinEndSec, blob, url, error, start, restart: start, stop, reset }
}
