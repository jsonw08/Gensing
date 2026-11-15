import { useCallback, useEffect, useRef, useState } from 'react'

export type Take = {
  id: number
  name: string // "Take 1", "Take 2", ...
  scoreName: string // file the take was sung against
  scoreXml: string // that file's MusicXML, so the take can be evaluated after the score changes
  tempoBpm: number | null // tempo it was sung at (quarter bpm); null = the score's marking
  countinEndSec: number // where beat 1 is in the recording (0 for uploads)
  blob: Blob
  url: string // object URL for playback / download
  durationMs: number
  savedAt: Date
}

export type NewTake = {
  blob: Blob
  durationMs: number
  scoreName: string
  scoreXml: string
  name?: string
  tempoBpm?: number | null
  countinEndSec?: number
}

// In-memory list of saved takes (lost on reload). Each take owns its object URL.
export function useTakes() {
  const [takes, setTakes] = useState<Take[]>([])
  const nextId = useRef(1)
  const urls = useRef(new Set<string>())

  const add = useCallback((t: NewTake) => {
    const id = nextId.current++
    const url = URL.createObjectURL(t.blob)
    urls.current.add(url)
    setTakes((prev) => [
      {
        id,
        name: t.name ?? `Take ${id}`,
        scoreName: t.scoreName,
        scoreXml: t.scoreXml,
        tempoBpm: t.tempoBpm ?? null,
        countinEndSec: t.countinEndSec ?? 0,
        blob: t.blob,
        url,
        durationMs: t.durationMs,
        savedAt: new Date(),
      },
      ...prev, // newest first
    ])
  }, [])

  const remove = useCallback((take: Take) => {
    URL.revokeObjectURL(take.url)
    urls.current.delete(take.url)
    setTakes((prev) => prev.filter((t) => t.id !== take.id))
  }, [])

  // Free every URL when the page unmounts.
  useEffect(() => {
    const set = urls.current
    return () => {
      set.forEach((u) => URL.revokeObjectURL(u))
      set.clear()
    }
  }, [])

  return { takes, add, remove }
}
