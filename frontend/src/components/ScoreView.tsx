import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'
import { useEffect, useRef } from 'react'

// Renders MusicXML with OSMD. Note coloring (stage 7) will hook in here.
export function ScoreView({ xml }: { xml: string }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const osmd = new OpenSheetMusicDisplay(containerRef.current, {
      autoResize: true,
      drawTitle: true,
    })
    let cancelled = false
    osmd.load(xml).then(() => {
      if (!cancelled) osmd.render()
    })
    return () => {
      cancelled = true
      osmd.clear()
    }
  }, [xml])

  return <div ref={containerRef} className="score" />
}
