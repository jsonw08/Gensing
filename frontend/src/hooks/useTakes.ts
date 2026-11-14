import { useCallback, useEffect, useRef, useState } from 'react'

export type Take = {
  id: number
  name: string // "Take 1", "Take 2", ...
  scoreName: string // file the take was sung against
  blob: Blob
  url: string // object URL for playback / download
  durationMs: number
  savedAt: Date
}

// In-memory list of saved takes (lost on reload). Each take owns its object URL.
export function useTakes() {
  const [takes, setTakes] = useState<Take[]>([])
  const nextId = useRef(1)
  const urls = useRef(new Set<string>())

  const add = useCallback((blob: Blob, durationMs: number, scoreName: string) => {
    const id = nextId.current++
    const url = URL.createObjectURL(blob)
    urls.current.add(url)
    setTakes((prev) => [
      { id, name: `Take ${id}`, scoreName, blob, url, durationMs, savedAt: new Date() },
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
