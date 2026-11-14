import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'
import { useEffect, useRef } from 'react'
import { collectNoteIds, NOTE_ID_OSMD_OPTIONS, type NoteIdEntry } from '../lib/noteIds'

// Renders MusicXML with OSMD. After each render, `onRendered` gets the note IDs (same scheme as the
// backend) with their noteheads, ready for coloring from results.notes.
export function ScoreView({
  xml,
  onRendered,
}: {
  xml: string
  onRendered?: (osmd: OpenSheetMusicDisplay, notes: NoteIdEntry[]) => void
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
    const osmd = new OpenSheetMusicDisplay(container, {
      autoResize: true,
      drawTitle: true,
      ...NOTE_ID_OSMD_OPTIONS, // required by the note-ID scheme (see lib/noteIds.ts)
    })
    let cancelled = false
    osmd.load(xml).then(() => {
      if (cancelled) {
        osmd.clear() // load finished after unmount: don't leave a ready-to-render instance
        return
      }
      osmd.render()
      onRenderedRef.current?.(osmd, collectNoteIds(osmd))
    })
    return () => {
      cancelled = true
      // clear() alone keeps OSMD's window-resize listener alive; a stale instance would then
      // redraw its own copy into this container on the next resize.
      osmd.AutoResizeEnabled = false
      osmd.clear()
      container.replaceChildren()
    }
  }, [xml])

  return <div ref={containerRef} className="score" />
}
