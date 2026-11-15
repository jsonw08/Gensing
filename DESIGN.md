---
name: Gensing
description: A late-90s platinum desktop where your sheet music comes back marked note by note.
colors:
  desk-periwinkle: "#7b86b8"
  desk-stripe: "#8590c2"
  platinum-face: "#e8e8e8"
  platinum-deep: "#d4d4d4"
  bevel-shade: "#8a8a8a"
  bevel-hilite: "#ffffff"
  frame-black: "#000000"
  ink: "#000000"
  ink-soft: "#3b3b3b"
  muted: "#5c5c5c"
  disabled-grey: "#9a9a9a"
  well-white: "#ffffff"
  balloon-cream: "#fffff2"
  counter-night: "#1d2030"
  select-indigo: "#3c4aa8"
  select-tint: "#dde1f7"
  in-tune: "#1f9d55"
  out-of-tune: "#d49b00"
  out-of-tune-dot: "#a87c00"
  wrong-note: "#d6334a"
  skipped: "#9a948c"
  timing: "#4b3fd1"
typography:
  display:
    fontFamily: "Silkscreen, Chivo Mono, monospace"
    fontSize: "64px"
    fontWeight: 400
    lineHeight: 0.9
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Silkscreen, Chivo Mono, monospace"
    fontSize: "40px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.02em"
  brand:
    fontFamily: "Silkscreen, Chivo Mono, monospace"
    fontSize: "14px"
    fontWeight: 400
    letterSpacing: "0.04em"
  title:
    fontFamily: "Chivo Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 700
  body:
    fontFamily: "Chivo Mono, ui-monospace, Menlo, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  body-reading:
    fontFamily: "Chivo Mono, ui-monospace, Menlo, monospace"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  ui:
    fontFamily: "Chivo Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Chivo Mono, ui-monospace, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  none: "0px"
  chip: "2px"
  swatch: "3px"
  button: "7px"
  band: "7px"
  balloon: "12px"
  round: "50%"
spacing:
  hair: "4px"
  xs: "6px"
  sm: "10px"
  md: "12px"
  lg: "14px"
  xl: "22px"
  desk: "28px"
components:
  button:
    backgroundColor: "{colors.platinum-face}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "3px 16px"
    height: "26px"
  button-pressed:
    backgroundColor: "#595959"
    textColor: "{colors.well-white}"
    rounded: "{rounded.button}"
  button-disabled:
    backgroundColor: "{colors.platinum-face}"
    textColor: "{colors.disabled-grey}"
    rounded: "{rounded.button}"
  icon-button:
    backgroundColor: "{colors.platinum-face}"
    rounded: "{rounded.button}"
    width: "30px"
    height: "26px"
  window:
    backgroundColor: "{colors.platinum-face}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  window-titlebar:
    backgroundColor: "{colors.platinum-face}"
    typography: "{typography.title}"
    height: "22px"
  window-body:
    padding: "12px"
  well:
    backgroundColor: "{colors.well-white}"
    rounded: "{rounded.none}"
  field:
    backgroundColor: "{colors.well-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "2px 6px"
    height: "26px"
  menubar:
    backgroundColor: "{colors.platinum-face}"
    height: "26px"
    padding: "0 10px"
  menu-item-active:
    backgroundColor: "{colors.select-indigo}"
    textColor: "{colors.well-white}"
    padding: "3px 18px 3px 4px"
  list-row-selected:
    backgroundColor: "{colors.select-indigo}"
    textColor: "{colors.well-white}"
    height: "28px"
  balloon:
    backgroundColor: "{colors.balloon-cream}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.balloon}"
    padding: "8px 12px"
  coach-tip:
    backgroundColor: "{colors.well-white}"
    padding: "11px 13px"
  coach-tip-selected:
    backgroundColor: "{colors.select-tint}"
  counter:
    backgroundColor: "{colors.counter-night}"
    textColor: "#e9ecff"
    padding: "8px 12px"
  score-dot:
    rounded: "{rounded.round}"
    size: "6px"
---

# Design System: Gensing

## Overview

**Creative North Star: "Working on a File"**

Gensing is a late-90s platinum desktop. Practising a piece is working on a document: the score is a document window, and the Results, Coach, Recorder and Takes are utility windows beside it on a periwinkle diagonal-stripe desktop. Everything is built from the period's own materials: 1px black frames, a 2px hard black window shadow, pinstriped title bars with a close box, bevelled platinum faces, white recessed wells, etched group boxes, a barber-pole progress bar, marching-ants selection and balloon help. It deliberately refuses the card-and-pill SaaS dashboard.

The desktop is calm so the score can be loud. Chrome is greyscale plus one selection indigo; the only saturated colour on a results screen is the verdict marking on the score (flat pastel bands and small dots) and the notes meter that sums it up. Type is monospaced throughout (Chivo Mono), with a pixel face (Silkscreen) reserved for the brand and for big numbers.

Windows sit in a fixed layout. They cannot be dragged, and the working screens are exactly one viewport tall: windows scroll inside, the desktop never does. The menus work (File, Take, View, Coach), with keyboard navigation.

**Key Characteristics:**
- Platinum windows with 1px black frames and a 2px hard black shadow on a striped periwinkle desktop.
- Square corners on everything structural; only buttons (7px), score bands (7px) and balloons (12px) are rounded.
- Chivo Mono for all UI text; Silkscreen only for the brand and big numerals.
- Five fixed verdict hues, shown on the score only as flat pastel bands and 6px dots.
- Pixel icons drawn from character grids, never icon fonts or emoji.
- Self-hosted fonts (@fontsource), so the demo works offline.

## Colors

A greyscale platinum chrome with one indigo for selection and focus, sitting on a periwinkle desk; all saturated colour belongs to the score's verdicts.

### Primary
- **Selection Indigo** (`select-indigo`): the system's one accent. Open menu title, hovered or focused menu item, selected list row, the focus ring (2px outline, 2px offset), text selection, the selected coach tip's border and its bar chips, the Practice drop-target outline, and the barber-pole stripe.
- **Selection Tint** (`select-tint`): the fill of a selected coach tip. Pale enough that body text stays fully legible.

### Neutral
- **Desk Periwinkle** and **Desk Stripe** (`desk-periwinkle`, `desk-stripe`): the desktop, as 2px/2px stripes at 45deg. `index.css` also paints the body periwinkle so nothing flashes before React draws.
- **Platinum Face** (`platinum-face`): window faces, the menu bar, button faces, menus, list headers.
- **Platinum Deep** (`platinum-deep`): reserved for toolbars and pressed wells (defined, lightly used).
- **Bevel Shade / Bevel Hilite** (`bevel-shade`, `bevel-hilite`): the two halves of every bevel and etch: hilite top-left, shade bottom-right on raised things; reversed on recessed wells. Bevel Shade also draws dotted leaders and menu separators.
- **Frame Black** (`frame-black`): every 1px frame and the window shadow. **Ink** is the same black for text; **Ink Soft** for secondary text (captions, player time, legend); **Muted** for hints, file names and meta lines; **Disabled Grey** for disabled text and borders.
- **Well White** (`well-white`): recessed areas: the score page, lists, fields, coach tips.
- **Balloon Cream** (`balloon-cream`): balloon help only.
- **Counter Night** (`counter-night`): the Recorder's dark LCD-style counter, with pale `#e9ecff` text.

### Verdict hues (fixed)
The team fixed these and they are not open to restyling: **In Tune** (`in-tune`), **Out of Tune** (`out-of-tune`), **Wrong Note** (`wrong-note`), **Skipped** (`skipped`), **Timing / early-late** (`timing`). They come from `STATUS_COLOR` and `TIMING_COLOR` in `lib/colorScore.ts` and are mirrored as CSS variables. **Out-of-Tune Dot** (`out-of-tune-dot`) is a darker gold used only for the 6px out-of-tune dot, because the band gold disappears as a small dot on white.

The Recorder lamp has its own hardware colours (idle `#6f6f6f`, count-in `#f2b318`, recording `#e3283f`, recorded `#2fbf6b`). They belong to the lamp component, not to the verdict system.

### Named Rules
**The Score Owns the Colour Rule.** Verdict hues appear only on the score (bands, dots), in the legend, in the notes meter and in the balloon's swatch. Chrome never borrows them, and no other saturated colour enters a results screen.

**The One Indigo Rule.** Selection and focus are always Selection Indigo. Don't introduce a second accent for "primary" actions; the default button is marked by its ring, not by colour.

## Typography

**Display Font:** Silkscreen (fallback Chivo Mono, monospace)
**Body Font:** Chivo Mono 400 and 700 (fallback ui-monospace, Menlo, monospace)

**Character:** a pixel face for the few things that should feel like a display readout, and a warm monospace for everything you read. Both are self-hosted via `@fontsource/silkscreen` and `@fontsource/chivo-mono`, so nothing loads from the network at the demo.

### Hierarchy
- **Display** (Silkscreen 400, 64px, line-height 0.9): the total score and the count-in beat. Steps down to 48px on short laptop screens (height ≤ 820px).
- **Headline** (Silkscreen 400, 40px): the Gensing name on the Welcome window. "Sing!" uses Silkscreen at 32px; the Recorder counter uses Silkscreen at 26px with tabular numbers.
- **Brand** (Silkscreen 400, 14px, 0.04em): the menu-bar brand.
- **Title** (Chivo Mono 700, 13px): window titles, group-box legends, list headers, coach section heads (14px).
- **Body** (Chivo Mono 400, 14px, 1.45): the contents of every window.
- **Body Reading** (Chivo Mono 400, 15px, 1.6): the coach summary and the Welcome lede; coach tips use 14px at 1.6.
- **UI** (Chivo Mono 400, 13px, 1.45): the desktop default (menus, toolbars, buttons).
- **Label** (Chivo Mono 400, 12-12.5px): legend, balloon text, hints, meta lines, bar chips.

Numbers that change or line up (scores, times, list columns, clock) use `font-variant-numeric: tabular-nums`.

### Named Rules
**The Pixel Is for Numbers Rule.** Silkscreen sets the brand and big numerals only. Never set sentences, buttons or labels in it.

**The Engraving Is Not UI Rule.** The score's own type (title, lyrics, dynamics) is OSMD's engraving, not the UI type. Don't restyle it with the UI fonts.

## Layout

Working screens (Practice, Results) are a grid: the score window on the left fills the full height (`minmax(0, 1fr)`), and a right column of `clamp(400px, 33vw, 500px)` holds two stacked windows. Gaps are 22px vertical and 26px horizontal, with 22px/28px/28px/24px desk padding. The screen is exactly one viewport tall (`.desk.fit`); windows scroll inside.

- Before feedback arrives, the Coach window is only as tall as its prompt (`align-self: start`), and the desktop shows below it.
- Count-in and "Sing!" dialogs float over the right column only, so the score stays readable.
- Short laptops (height ≤ 820px, width > 1080px): the Results window tightens (gap 9px, total 48px, the four parts in two columns).
- At 1080px wide and below, windows stack into one column, the score window becomes 80vh, and the desktop scrolls. The target is a laptop at 1280-1600px wide.
- Welcome is a single centred window, at most 600px wide; at 600px and below its padding drops to 16px.

Inside windows, the spacing rhythm is 4 / 6 / 10 / 12 / 14px: 12px body padding, 14px between stacked blocks, 10px between buttons, 6-8px between an icon and its label.

## Elevation & Depth

Depth is literal and hard-edged, the way a 90s desktop drew it: no blur, no ambient shadow. Raised things (window faces, buttons, close boxes, scrollbar thumbs, slider thumbs) get an inset bevel, hilite top-left and shade bottom-right. Recessed things (wells, fields, the radio dot's socket, the counter) get the reverse. Windows sit on the desk with a solid offset shadow.

### Shadow Vocabulary
- **Window shadow** (`box-shadow: 2px 2px 0 #000`): every window, plus the outer edge of dialogs.
- **Menu / balloon drop** (`2px 2px 0 rgba(0,0,0,0.55)` for menus, `rgba(0,0,0,0.3)` for balloons): pop-ups that float above windows.
- **Raised bevel** (`inset 1px 1px 0 #fff, inset -1px -1px 0 #8a8a8a`): buttons, close box, scrollbar and slider thumbs.
- **Recessed well** (`-1px -1px 0 #8a8a8a, 1px 1px 0 #fff` outside a 1px black frame): the score page, lists, the notes meter, the counter. Fields use `inset 1px 1px 0 #8a8a8a`.
- **Pressed** (`inset 1px 1px 0 #2f2f2f` on `#595959` with white text): a button while held.
- **Dialog double frame** (`inset 0 0 0 3px face, inset 0 0 0 4px shade, 2px 2px 0 #000`).

### Named Rules
**The Hard Shadow Rule.** Shadows are solid offsets of 2px or less, never blurred. The 2px black window shadow is native to this world, not decoration; it belongs on windows and dialogs, and nothing else gets a heavier one.

## Shapes

Structural shapes are square: windows, wells, fields, menus, list rows, the counter, the progress bar, group boxes. Roundness is reserved for things that were round on the period desktop or that sit on the music:

- Buttons: 7px radius (`rounded.button`).
- Score highlight bands: 7px radius (`rounded.band`).
- Balloon help: 12px radius with a skewed tail pointing at the note.
- Radio buttons, score dots, the status lamp: circles.
- Legend swatches 3px, inline colour chips 2px.

Lines are 1px. Dotted 1px Bevel Shade lines are the leader and separator (score rows, menu separators). The close box is a 13px bevelled square at the title bar's left.

## Components

### Buttons
Bevelled platinum lozenges that press in.
- **Shape:** gently rounded (7px), 1px black frame, min-height 26px, padding 3px 16px.
- **Default:** platinum face with the raised bevel.
- **Default button (what Return does):** the same button wearing a 2px black ring at a 2px offset (`.button.default`, with a 3px margin to make room). One per window at most: "Get started", "Open score…", "Record", "Evaluate", "Get feedback". ("Sing it again" is a plain button.)
- **Pressed:** dark grey (#595959) face, white text, inset shadow.
- **Focus:** 2px Selection Indigo outline; on a default button the ring itself turns indigo.
- **Disabled:** grey text and border; the default ring turns grey.
- **Icon button:** 30px wide, pixel icon centred (the player's play/pause).

### Windows
- **Frame:** platinum face, 1px black border, 2px hard black shadow, square corners.
- **Title bar:** 22px, centred bold 13px title on a face-coloured plate over 1px pinstripes (#a3a3a3 on face), 13px close box at left (decorative; windows don't close or drag).
- **Toolbar** (optional): under the title bar, 7px 10px padding, etched bottom edge. Holds the player and a right-aligned muted note.
- **Body:** 12px padding, scrolls internally.
- **Footer** (optional): etched top edge, buttons right-aligned (left-aligned in Takes, with a spacer before the default button).

### Wells and fields
- **Well:** white, 1px black frame, recessed bevel. The score page, the takes list and the notes meter are wells.
- **Field:** white, 1px frame, inset shade, square, 26px tall.
- **Radio:** 13px circle, white, inset shade; checked shows a 2.5px black centre. Radios sit in an etched **group box** (fieldset with a bold legend), labelled rows on a 64px label column.
- **Slider:** 6px white recessed track, 11x16px bevelled rectangular thumb.

### Navigation (menu bar)
- 26px platinum bar, sticky, 1px black bottom edge. Brand at left (pixel note icon + "Gensing" in Silkscreen 14px), menu titles at 11px side padding, clock at right with tabular numbers.
- An open title and the hovered or focused item invert to Selection Indigo with white text. Menus are square platinum lists with a 2px drop shadow, a 20px check column (pixel check icon), and dotted separators. Arrow keys, Enter and Escape work.

### Lists (Takes)
A file-list view inside a well: a 22px sticky bevelled header row in bold 12.5px, 28px rows on a three-column grid (name, length, saved), odd rows `#f4f5fb`, the selected row Selection Indigo with white text. Each row name leads with the pixel note icon.

### Dialogs and progress
- **Dialog box:** double-framed platinum box (inner etched line), pixel icon at left (2x), text, right-aligned actions. Used inside the score page (over a 72% white veil) and over the right column for the count-in.
- **Progress:** indeterminate barber pole, 13px tall, indigo and #c9cef0 stripes at -45deg moving at 0.9s; static under reduced motion.
- **Count-in:** Silkscreen beat number (64px) and a row of 12px square beat cells that fill black.

### Recorder counter and lamp
A recessed dark counter (Counter Night) with the status text and a Silkscreen time readout. The 11px lamp is grey idle, amber during the count-in, red blinking (1s, two steps) while recording, green once recorded; it stops blinking under reduced motion.

### Results window
The total in Silkscreen display with a two-line caption ("out of 100", "N of M notes in tune"); the four parts (Pitch, Intonation, Rhythm, Completeness) as rows with dotted leaders and bold tabular values; the notes meter (a 12px well split into verdict-coloured segments, 1px white separators); meta lines in Muted 12.5px; the Grading group box (Timing, Level radio rows). The total greys out and a barber pole shows while re-scoring.

### Coach window
Before feedback: the pixel note icon (2x), one prompt sentence and the "Get feedback" default button. After: a 15px summary, "What went well" bullets, then "What to work on" tips as white boxes (1px shade border, 11px 13px padding). A tip naming bars is clickable: hover darkens its border to black; selected turns Selection Tint with an indigo double border and indigo bar chips, and the score selects those bars with marching ants.

### Score marking (signature component)
The score is OSMD's own engraving inside the white page well, lightened: zoom 0.9, staff lines 0.08 in #3d3d3d, stems 0.12, more room between systems and above the first line (for the dot row), lyrics pushed further from the staff so bands never touch words. No part names and no metronome marks. Noteheads stay black.

- **Bands:** flat pastel boxes over each note's column, from the top staff line to the bottom one plus 12px (stretched only for ledger-line notes), 7px padding either side, 7px radius, `mix-blend-mode: multiply` so the black notes stay crisp. Problem bands (out of tune, wrong, skipped) at 0.26 opacity; in-tune bands are subtle at 0.10, so problems stand out. Uncertain notes are faded (0.12 problem, 0.05 in tune). Consecutive notes with the same verdict on the same line join into one band; a rest, a different verdict or a line break ends it.
- **Dots:** one 6px circle above each problem note: band colour for wrong or out of tune (out of tune uses the darker dot gold), Timing indigo for early/late on an otherwise in-tune note, none for skipped. All dots on a line of music share one baseline, raised above tuplets, slurs, ties and tempo words. Uncertain dots at 0.4 opacity. Dots are buttons, so Tab reaches them; a 7px invisible margin enlarges the target.
- **Balloon help:** cream balloon, 1px frame, 12px radius, skewed tail pointing at the note, 12px text. A colour swatch and the note name (with its lyric), then one line per fact: "Out of tune · 38 cents flat", "140 ms late", "Wrong note · sang F#4", "Hard to hear: not scored". It flips below the note near the top of the page and is clamped inside the page sideways.
- **Extra notes:** no mark on the score. They are listed only in the balloon of the note or rest they followed ("An extra note after: sang G4"); a rest with extras gets an invisible hover area.
- **Bar selection:** marching ants (1px black dashes, 8px period, 0.6s), reaching up past the dot row; static under reduced motion. The page scrolls to centre the first selected bar.
- **Legend:** a strip under the page, outside the scroll: swatches (16x12px, 3px radius, hairline edge) mixed with white at 30% for problems and 16% for in tune, a Timing dot for "Early / late", and the hint "Point at a dot for details" at right.

### Icons
Pixel icons drawn from character grids (`components/desktop/Icon.tsx`: play, pause, note, caution, check), rendered as crisp-edged SVG rects in `currentColor` (caution adds yellow #F7D23E). Scale only by whole multiples (1x, 2x).

## Do's and Don'ts

### Do:
- **Do** build every new surface as a window: platinum face, 1px black frame, 2px hard black shadow, pinstriped 22px title bar with a close box, square corners.
- **Do** put recessed content (lists, pages, inputs) in a white well with the reversed bevel.
- **Do** use Selection Indigo for every selected, open, hovered-menu and focused state, and the 2px indigo focus outline at a 2px offset.
- **Do** mark the one Return action in a window with the default-button ring.
- **Do** keep the verdict hues exactly as defined and show them on the score only as flat pastel bands (problems 0.26, in tune 0.10) and 6px dots.
- **Do** put note details in the balloon (cents flat or sharp, ms early or late, what was sung, extras), using the product's verdict words.
- **Do** draw new icons as pixel grids in `Icon.tsx`.
- **Do** honour `prefers-reduced-motion`: barber pole, marching ants and the recording blink all stop.
- **Do** check score-marking changes against error-heavy takes (the `mistakes` takes, e.g. lantern-song), not only the clean `perfect` ones: the team caught marking regressions this way that clean takes hide.
- **Do** keep fonts self-hosted through @fontsource; the demo must work offline.

### Don't:
- **Don't** add text tags, pills or labels on the score for verdicts; the band, the dot and the balloon carry it.
- **Don't** give extra notes a mark of their own (no "+" glyphs); they live only in the balloon.
- **Don't** colour noteheads or restyle OSMD's engraving fonts.
- **Don't** use rounded cards, pill buttons, soft blurred shadows or gradients-as-decoration; this is not a SaaS dashboard.
- **Don't** make windows draggable or closable, or let the working screens scroll the desktop above 1080px wide.
- **Don't** use emoji, icon fonts or text glyphs as icons, or set sentences in Silkscreen.
- **Don't** use Apple's logo, the Chicago font or the Happy Mac; Gensing uses its own icons and fonts.
- **Don't** load fonts or scripts from a CDN at runtime.
