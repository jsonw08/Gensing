import { useCallback, useEffect, useRef } from 'react'
import { claimPlayback } from '../lib/exclusivePlayback'
import { audioContext } from '../lib/metronome'

const LEAD_SEC = 0.1 // start a little before the note, so its attack isn't cut
const TAIL_SEC = 0.15 // and let it ring a little after
const FADE_SEC = 0.015 // short fades, so the cut edges don't click

// Plays one stretch of a recording: click a note, hear just that note. Uses Web Audio (sample-accurate
// start and stop); an <audio> element only reports its position a few times a second. The recording is
// decoded once, on the first click. A new snippet stops the one still playing, and so does the take
// player starting; a snippet starting pauses the take player (lib/exclusivePlayback).
export function useSnippet(recording: Blob) {
  const bufferRef = useRef<Promise<AudioBuffer> | null>(null)
  const playingRef = useRef<AudioBufferSourceNode | null>(null)

  const stop = useCallback(() => {
    try {
      playingRef.current?.stop()
    } catch {
      /* already stopped */
    }
    playingRef.current = null
  }, [])

  // A different recording: forget the decoded one. Unmount: stop playing.
  useEffect(() => {
    bufferRef.current = null
    return stop
  }, [recording, stop])

  /** Play [startSec, endSec] of the recording (its own timeline, in seconds). */
  const play = useCallback(
    async (startSec: number, endSec: number) => {
      const ctx = audioContext() // resumes inside the click (browsers need a user gesture)
      stop()
      if (!bufferRef.current) {
        const decoding = recording.arrayBuffer().then((b) => ctx.decodeAudioData(b))
        decoding.catch(() => {
          if (bufferRef.current === decoding) bufferRef.current = null // try again on the next click
        })
        bufferRef.current = decoding
      }
      const buffer = await bufferRef.current
      const from = Math.max(0, startSec - LEAD_SEC)
      const to = Math.min(buffer.duration, endSec + TAIL_SEC)
      if (to <= from) return
      const length = to - from

      const src = ctx.createBufferSource()
      src.buffer = buffer
      const gain = ctx.createGain()
      const t = ctx.currentTime + 0.01
      gain.gain.setValueAtTime(0, t)
      gain.gain.linearRampToValueAtTime(1, t + FADE_SEC)
      gain.gain.setValueAtTime(1, t + Math.max(FADE_SEC, length - FADE_SEC))
      gain.gain.linearRampToValueAtTime(0, t + length)
      src.connect(gain).connect(ctx.destination)
      stop() // a quicker second click may have started one while this one was decoding
      const release = claimPlayback(() => {
        if (playingRef.current === src) stop()
      }) // pauses the take player
      src.start(t, from, length)
      playingRef.current = src
      src.onended = () => {
        release()
        if (playingRef.current === src) playingRef.current = null
      }
    },
    [recording, stop],
  )

  return { play, stop }
}
