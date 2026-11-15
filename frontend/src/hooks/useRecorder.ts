import { useCallback, useEffect, useRef, useState } from 'react'
import { audioContext, audioTimeToPerf, heardAudioTime, scheduleClicks, warmUp } from '../lib/metronome'
import { trimStartToWav } from '../lib/wav'

export type RecorderStatus = 'idle' | 'countin' | 'recording' | 'stopped'

export type CountIn = { beats: number; intervalSec: number }

// After first opening the mic, before the first click. Opening the mic can switch the audio output (e.g.
// Bluetooth headphones into headset mode); clicks played during the switch are lost, so wait it out.
const MIC_SETTLE_MS = 1000
const CLICK_LEAD_SEC = 0.25 // schedule the first click this far ahead

// Microphone recorder with a count-in, stop and restart, built on MediaRecorder.
//
// The mic starts BEFORE the count-in (starting it at beat 1 would add the browser's variable start-up
// delay), so the raw recording begins with the clicks. When it stops, everything before beat 1 is cut off
// and the take is saved as a WAV that starts at beat 1: no clicks on playback, and `countinEndSec` is 0.
// If cutting fails, the raw recording (WebM/MP4) is kept and `countinEndSec` says where beat 1 is in it
// (sent to /analyze as countin_end_sec, which trims it there; stage 5 also removes the remaining latency).
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
        let beatOneSec = 0 // where beat 1 is in this recording; 0 until the count-in is over
        rec.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data)
        }
        rec.onstop = async () => {
          if (recRef.current !== rec) return // discarded (restart / reset / unmount)
          const raw = new Blob(chunks, { type: rec.mimeType })
          let take: Blob = raw
          let cut = beatOneSec
          if (beatOneSec > 0) {
            try {
              take = await trimStartToWav(raw, beatOneSec) // drop the count-in clicks
              cut = 0
            } catch (err) {
              console.warn('[recorder] could not cut off the count-in; keeping the full recording', err)
            }
          }
          if (recRef.current !== rec) return // discarded while cutting
          setCountinEndSec(cut)
          setTake(take)
          setStatus('stopped')
        }
        recRef.current = rec
        rec.start()
        const recStartedAt = performance.now()

        const beginSinging = (atPerf: number) => {
          beatOneAtRef.current = atPerf
          beatOneSec = Math.max(0, (atPerf - recStartedAt) / 1000)
          setCountinEndSec(beatOneSec)
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
        // One line per count-in, to diagnose clicks that aren't heard (device switches, a stuck context).
        console.info('[count-in]', { micJustOpened: fresh, audio: ctx.state, outputLatency: ctx.outputLatency, sampleRate: ctx.sampleRate })

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

  // Open the mic ahead of time (e.g. once a score is chosen), so the permission prompt and any audio device
  // switch it causes happen before the first take's count-in, not during it. Errors surface on Record.
  const warmMic = useCallback(() => {
    openMic().catch(() => {})
  }, [openMic])

  // restart = start again (throws the current take away); it takes the same count-in argument.
  return { status, elapsedMs, countInBeat, countinEndSec, blob, url, error, start, restart: start, stop, reset, warmMic }
}
