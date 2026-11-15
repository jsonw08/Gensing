---
version: 1
slug: "frontend-src-pages-evaluate-tsx"
primary_target: "frontend/src/pages/Evaluate.tsx"
related_targets: ["frontend/src/pages/Practice.tsx","frontend/src/pages/Welcome.tsx"]
---

## Scope

All three screens of the Gensing web app (Welcome, Practice, Results). Mode: Operate. Results is the key surface: the marked-up score is the demo moment.

## Direction contract

THESIS: Gensing is a late-90s platinum desktop, and practising is "working on a file": the score is a document window, the score card and the coach are utility windows beside it. It refuses the category default of a card-and-pill SaaS dashboard.

OWN-WORLD: Periwinkle diagonal-stripe desktop (#7B86B8/#8590C2); platinum faces #E8E8E8 with 1px black frames, 2px hard black window shadow, pinstriped title bars with a close box; white recessed wells; bevelled 7px-radius buttons, the default one ringed; radio buttons in etched group boxes; barber-pole progress; marching-ants selection; balloon-help tooltips; pixel icons drawn from grids. Type: Silkscreen for the brand and the big score, Chivo Mono for everything else. Highlight band colours on the score are unchanged from the previous design.

STORY: The singer sees their own sheet music come back marked note by note, the score in big pixel numerals, and a coach who points at bars. They understand what went wrong where, and sing it again.

FIRST VIEWPORT: Menu bar (♪ GENSING, File, Take, View, Coach, clock). Left: Score window filling the height, toolbar with a retro player, the white page (OSMD, lighter engraving) with flat pastel highlight bands (same-verdict runs joined) and one row of small dots above problem notes, details in a balloon-help tooltip (no text tags; extra notes only in the balloon), legend strip at the bottom. Right column clamp(400px, 33vw, 500px): Results window (pixel total, four parts with dotted leaders, notes meter, one Grading box with Timing/Level radio rows, "Sing it again"), Coach window below (sized to its prompt until feedback arrives; "Get feedback" default button; tips that select bars on the score with marching ants).

FORM: Retro desktop (sketch 9 of the exploration gallery), chosen by the team. seed: none (pinned) "our group likes the wild: retro desktop one". Fixed window layout (no dragging); full desktop with working menus.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Constraints

- Keep OSMD rendering and the highlight band colours; markers may change.
- Use our own icons and fonts: no Apple logo, Chicago font or Happy Mac.
- Desktop laptop at 1280-1600 wide is the target; under 1080 wide the windows stack.
