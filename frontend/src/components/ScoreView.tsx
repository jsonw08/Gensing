import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'
import { type ReactNode, useEffect, useRef } from 'react'
import { collectNoteIds, NOTE_ID_OSMD_OPTIONS, type NoteIdEntry } from '../lib/noteIds'

// Renders MusicXML with OSMD. After EVERY render (first load and each resize) `onRendered` gets the
// note IDs (same scheme as the backend) with their noteheads, so coloring can be re-applied: OSMD
// redraws the SVG from scratch each time. `children` is drawn over the score (marker overlay).
export function ScoreView({
  xml,
  onRendered,
  children,
}: {
  xml: string
  onRendered?: (osmd: OpenSheetMusicDisplay, notes: NoteIdEntry[]) => void
  children?: ReactNode
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onRenderedRef = useRef(onRendered)
  useEffect(() => {
    onRenderedRef.current = onRendered
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.replaceChildren() // drop anything a previous instance drew
    // autoResize off: we redraw ourselves (below) so we know when to re-apply colors.
    const osmd = new OpenSheetMusicDisplay(container, {
      autoResize: false,
      drawTitle: true,
      ...NOTE_ID_OSMD_OPTIONS, // required by the note-ID scheme (see lib/noteIds.ts)
    })
    let cancelled = false
    let loaded = false
    let lastWidth = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    const draw = () => {
      lastWidth = container.clientWidth
      osmd.render()
      onRenderedRef.current?.(osmd, collectNoteIds(osmd))
    }

    // Redraw when the score's width changes (window resize, layout change), debounced.
    const observer = new ResizeObserver(() => {
      if (!loaded || Math.abs(container.clientWidth - lastWidth) < 2) return
      clearTimeout(timer)
      timer = setTimeout(draw, 150)
    })
    observer.observe(container)

    osmd.load(xml).then(() => {
      if (cancelled) {
        osmd.clear() // load finished after unmount: don't leave a ready-to-render instance
        return
      }
      loaded = true
      draw()
    })
    return () => {
      cancelled = true
      observer.disconnect()
      clearTimeout(timer)
      osmd.clear()
      container.replaceChildren()
    }
  }, [xml])

  return (
    <div className="score-wrap">
      <div ref={containerRef} className="score" />
      {children}
    </div>
  )
}
