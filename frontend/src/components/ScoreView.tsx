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
      drawPartNames: false, // one voice: the "Voice" label only pushes the music right
      drawMetronomeMarks: false, // the tempo is set (and shown) on the Practice screen
      drawMeasureNumbersOnlyAtSystemStart: true,
      ...NOTE_ID_OSMD_OPTIONS, // required by the note-ID scheme (see lib/noteIds.ts)
    })
    // A lighter, airier engraving: smaller title and lyrics, finer lines, more room between lines of
    // music and between the staff and the lyrics (so highlight bands never touch the words).
    const rules = osmd.EngravingRules
    rules.SheetTitleHeight = 3
    rules.SheetComposerHeight = 1.5
    rules.LyricsHeight = 1.85
    rules.LyricsYOffsetToStaffHeight = 0.6
    rules.StaffLineWidth = 0.08
    rules.StaffLineColor = '#3d3d3d'
    rules.StemWidth = 0.12
    rules.MinimumDistanceBetweenSystems = 9
    rules.SystemComposerDistance = 4.5 // room for the row of result dots above the first line
    rules.VoiceSpacingMultiplierVexflow = 1.0 // roomier note spacing (about 4 bars of 4/4 per line)
    let cancelled = false
    let loaded = false
    let lastWidth = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    const draw = () => {
      lastWidth = container.clientWidth
      osmd.zoom = 0.9 // slightly smaller than OSMD's default: the score shares the screen with two windows
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
