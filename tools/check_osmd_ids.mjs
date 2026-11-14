// Proves the note-ID contract end to end: stage 1 (music21, backend) and OSMD (frontend renderer)
// must give every note the same ID, and every ID must have a drawn notehead to color.
//
//   npm run check:osmd-ids                  # every file (samples + real-world OSMD test files)
//   npm run check:osmd-ids -- beethoven     # one file (names: npm run inspect:score)
//   npm run check:osmd-ids -- all --osmd-defaults   # same, with OSMD's default options (shows the multi-rest problem)
//
// For each file it:
//   1. gets stage 1's expected_notes (backend/tests/manual/inspect_score.py --dump-json),
//   2. loads + renders the same file in real OSMD (Node + jsdom, no browser) with FRONTEND_OSMD_OPTIONS,
//   3. builds IDs from OSMD's data with collectNoteIds() (the recipe in docs/DECISIONS.md section 3),
//   4. compares id / rest / midi / onset / duration / render_ids, and checks each render_id has an SVG notehead.
//
// collectNoteIds() is written to be copied into the frontend as is.

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PYTHON = path.join(REPO, "backend/.venv/bin/python");
const INSPECT = path.join(REPO, "backend/tests/manual/inspect_score.py");

/** Options the frontend must use. Multi-rest off: otherwise several empty bars in a row are drawn as
 *  one symbol and those rests get no notehead (extras placed "during a rest" would have nowhere to go). */
export const FRONTEND_OSMD_OPTIONS = { autoGenerateMultipleRestMeasuresFromRestMeasures: false };

// --------------------------------------------------------------------------- the recipe

/**
 * Build our note IDs from a loaded (and, for `graphical`, rendered) OSMD instance.
 * Rules (docs/DECISIONS.md section 3): first part, voice 1; bars by position in the file from 1
 * (SourceMeasures index, NOT MeasureNumber, which is the printed number: pickups print as 0);
 * index from 0 in time order; rests count; grace notes skipped; chord = one index (top note);
 * tie continuation takes an index but no entry: its ID goes into the first notehead's render_ids.
 *
 * Returns entries in score order: { id, is_rest, midi, onset_beats, duration_beats, render_ids,
 * graphical: { [renderId]: GraphicalNote[] } } -- color every GraphicalNote of every render id.
 */
export function collectNoteIds(osmd) {
  const rules = osmd.EngravingRules;
  const entries = [];
  osmd.Sheet.SourceMeasures.forEach((measure, i) => {
    const bar = i + 1;
    // Voice entries on the first staff of the first instrument (= music21's first part), grace skipped
    const onStaff = [];
    for (const container of measure.VerticalSourceStaffEntryContainers) {
      const staffEntry = container.StaffEntries[0];
      if (!staffEntry) continue;
      for (const ve of staffEntry.VoiceEntries) {
        if (!ve.IsGrace) onStaff.push({ ve, onset: measure.AbsoluteTimestamp.RealValue + container.Timestamp.RealValue });
      }
    }
    const voiceIds = [...new Set(onStaff.map((x) => x.ve.ParentVoice.VoiceId))];
    const voiceOne = voiceIds.includes(1) ? 1 : voiceIds[0]; // "voice 1", else the first voice in the bar
    let index = 0;
    for (const { ve, onset } of onStaff.filter((x) => x.ve.ParentVoice.VoiceId === voiceOne)) {
      const id = `m${bar}-n${index++}`;
      const notes = ve.Notes;
      const isRest = notes[0].isRest();
      const top = isRest ? null : notes.reduce((a, b) => (b.Pitch.getHalfTone() > a.Pitch.getHalfTone() ? b : a));
      const graphical = notes.map((n) => rules.GNote(n)).filter(Boolean);
      const prev = entries[entries.length - 1];
      const tieContinuation = top && top.NoteTie && top.NoteTie.StartNote !== top;
      if (tieContinuation && prev && !prev.is_rest) {
        prev.render_ids.push(id);
        prev.duration_beats += notes[0].Length.RealValue * 4;
        prev.graphical[id] = graphical;
        continue;
      }
      entries.push({
        id,
        is_rest: isRest,
        midi: isRest ? null : top.Pitch.getHalfTone() + 12, // OSMD half tones: C4 = 48
        onset_beats: onset * 4, // OSMD timestamps are in whole notes; ours are quarter beats
        duration_beats: notes[0].Length.RealValue * 4,
        render_ids: [id],
        graphical: { [id]: graphical },
      });
    }
  });
  return entries;
}

// --------------------------------------------------------------------------- OSMD in Node

function makeOsmd(OpenSheetMusicDisplay, options) {
  const dom = new JSDOM("<!doctype html><html><body><div id='score'></div></body></html>", { pretendToBeVisual: true });
  for (const k of ["window", "document", "DOMParser", "Node", "HTMLElement", "SVGElement", "navigator", "XMLSerializer"]) {
    // defineProperty, not assignment: Node 21+ has a read-only global `navigator`
    Object.defineProperty(globalThis, k, { value: dom.window[k], configurable: true, writable: true });
  }
  // OSMD measures text on a canvas; jsdom has none. A fake 2D context is enough: we read data, not pixels.
  const ctx = new Proxy(
    { measureText: (t) => ({ width: String(t).length * 6, actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 }) },
    { get: (o, k) => (k in o ? o[k] : () => {}), set: () => true },
  );
  dom.window.HTMLCanvasElement.prototype.getContext = () => ctx;
  const div = dom.window.document.getElementById("score");
  Object.defineProperty(div, "offsetWidth", { get: () => 1000 });
  return new OpenSheetMusicDisplay(div, { autoResize: false, backend: "svg", ...options });
}

// --------------------------------------------------------------------------- compare

const round = (x) => (x === null ? null : Math.round(x * 1e4) / 1e4);
const key = (n) => JSON.stringify([n.id, n.is_rest, n.midi, round(n.onset_beats), round(n.duration_beats), n.render_ids]);

function stage1(name) {
  const out = execFileSync(PYTHON, [INSPECT, name, "--dump-json"], { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });
  return JSON.parse(out);
}

async function check(name, OpenSheetMusicDisplay, options) {
  const { path: file, expected_notes: expected } = stage1(name);
  const osmd = makeOsmd(OpenSheetMusicDisplay, options);
  const binary = file.endsWith(".mxl");
  await osmd.load(fs.readFileSync(file, binary ? "binary" : "utf8"));
  osmd.render();
  const ours = expected.notes;
  const theirs = collectNoteIds(osmd);

  const problems = [];
  if (ours.length !== theirs.length) problems.push(`entry count: stage 1 ${ours.length}, OSMD ${theirs.length}`);
  for (let i = 0; i < Math.min(ours.length, theirs.length); i++) {
    if (key(ours[i]) !== key(theirs[i])) problems.push(`stage 1 ${key(ours[i])}\n         OSMD    ${key(theirs[i])}`);
  }
  const renderIds = theirs.flatMap((e) => e.render_ids.map((rid) => [rid, e.graphical[rid]]));
  const undrawn = renderIds.filter(([, g]) => !g.length || !g.every((gn) => gn.getSVGGElement?.())).map(([rid]) => rid);

  const ok = problems.length === 0 && undrawn.length === 0;
  console.log(
    `${ok ? "OK  " : "FAIL"} ${name.padEnd(15)} ${ours.length} entries: ` +
      `${problems.length ? `${problems.length} ID mismatches` : "IDs identical"}, ` +
      `${renderIds.length - undrawn.length}/${renderIds.length} noteheads drawn`,
  );
  for (const p of problems.slice(0, 5)) console.log(`       ${p}`);
  if (undrawn.length) console.log(`       no notehead for: ${undrawn.slice(0, 12).join(", ")}${undrawn.length > 12 ? ", ..." : ""}`);
  return ok;
}

async function main() {
  const args = process.argv.slice(2);
  const defaults = args.includes("--osmd-defaults");
  const target = args.find((a) => !a.startsWith("--")) ?? "all";
  const names = target === "all" ? JSON.parse(execFileSync(PYTHON, [INSPECT, "--names"], { encoding: "utf8" })) : [target];

  const require = createRequire(path.join(REPO, "frontend/package.json"));
  const { OpenSheetMusicDisplay } = require("opensheetmusicdisplay");
  const version = JSON.parse(fs.readFileSync(path.join(REPO, "frontend/node_modules/opensheetmusicdisplay/package.json"), "utf8")).version;
  console.log(`OSMD ${version}, options: ${defaults ? "OSMD defaults" : JSON.stringify(FRONTEND_OSMD_OPTIONS)}\n`);

  let allOk = true;
  for (const name of names) allOk = (await check(name, OpenSheetMusicDisplay, defaults ? {} : FRONTEND_OSMD_OPTIONS)) && allOk;
  console.log(allOk ? "\nAll files: stage 1 IDs match OSMD, and every ID has a notehead." : "\nSome files FAILED (see above).");
  process.exit(allOk ? 0 : 1);
}

main();
