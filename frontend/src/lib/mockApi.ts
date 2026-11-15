import type { AnalyzeResponse, Feedback } from './api'

// Mock backend for testing the UI without the API (`npm run dev:mock`). Picks made-up results by the
// score's title, after a short delay so loading states show. Loaded on demand: not in the normal bundle.
//
//   C Major Scale (test)  contracts/*.sample.json (the contract samples)
//   Lantern Song          src/mocks/lantern-song.* (expected_notes from stage 1; planted mistakes:
//                         every error type, both ties, accidental and key-change slips, an uncertain note)
//
// Any other score fails with a message, so colors never land on the wrong piece.

type Mock = {
  analyze: () => Promise<AnalyzeResponse>
  feedback: () => Promise<Feedback>
}

const parse = (m: { default: string }) => JSON.parse(m.default)

const MOCKS: Record<string, Mock> = {
  'C Major Scale (test)': {
    analyze: async () => {
      const [results, expected, sung, track] = await Promise.all([
        import('../../../contracts/results.sample.json?raw'),
        import('../../../contracts/expected_notes.sample.json?raw'),
        import('../../../contracts/sung_notes.sample.json?raw'),
        import('../../../contracts/pitch_track.sample.json?raw'),
      ])
      return { results: parse(results), expected_notes: parse(expected), sung_notes: parse(sung), pitch_track: parse(track) }
    },
    feedback: async () => parse(await import('../../../contracts/feedback.sample.json?raw')),
  },
  'Lantern Song': {
    analyze: async () => {
      const [results, expected] = await Promise.all([
        import('../mocks/lantern-song.results.json?raw'),
        import('../mocks/lantern-song.expected_notes.json?raw'),
      ])
      // No audio-side mocks for this piece: the UI only uses `results`.
      return { results: parse(results), expected_notes: parse(expected), sung_notes: null, pitch_track: null }
    },
    feedback: async () => parse(await import('../mocks/lantern-song.feedback.json?raw')),
  },
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

function scoreTitle(xml: string): string | null {
  const doc = new DOMParser().parseFromString(xml, 'application/xml')
  const t = doc.querySelector('work > work-title')?.textContent ?? doc.querySelector('movement-title')?.textContent
  return t?.trim() || null
}

export async function mockAnalyze(musicxml: File): Promise<AnalyzeResponse> {
  await wait(800)
  const title = scoreTitle(await musicxml.text())
  const mock = title ? MOCKS[title] : undefined
  if (!mock) throw new Error(`no mock results for "${title ?? musicxml.name}" (mocks exist for: ${Object.keys(MOCKS).join(', ')})`)
  return mock.analyze()
}

export async function mockFeedback(results: { meta?: { title?: string } }): Promise<Feedback> {
  await wait(1500)
  const mock = MOCKS[results.meta?.title ?? '']
  if (!mock) throw new Error('no mock feedback for this score')
  return mock.feedback()
}
