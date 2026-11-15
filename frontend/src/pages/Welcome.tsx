import { Icon } from '../components/desktop/Icon'
import { type Menu, MenuBar } from '../components/desktop/MenuBar'
import { Window } from '../components/desktop/Window'

// The first screen: a welcome window on the desktop that says what Gensing does and shows it (a bar of
// Twinkle, Twinkle, marked up the way the Results screen marks a take), then one way in.
export function Welcome({ onStart }: { onStart: () => void }) {
  const menus: Menu[] = [
    { label: 'File', items: [{ label: 'Open score…', onSelect: onStart }] },
    { label: 'View', items: [{ label: 'Practice', onSelect: onStart }] },
  ]
  return (
    <div className="desk fit">
      <MenuBar menus={menus} />
      <main className="welcome-desk">
        <Window
          title="Welcome to Gensing"
          className="welcome-window"
          footer={
            <button type="button" className="button default" onClick={onStart} autoFocus>
              Get started
            </button>
          }
        >
          <div className="welcome-head">
            <Icon name="note" size={3} />
            <h1 className="welcome-name">Gensing</h1>
          </div>
          <p className="welcome-lede">Your sheet music, marked up like a voice teacher would.</p>

          <figure className="welcome-sample well">
            <SampleBar />
          </figure>

          <ol className="welcome-steps">
            <li>Open a MusicXML score.</li>
            <li>Sing it after a one-bar count-in.</li>
            <li>See every note marked, with tips.</li>
          </ol>
        </Window>
      </main>
    </div>
  )
}

// Two bars of "Twinkle, Twinkle" as a take might come back: a green run, one flat note (amber band +
// dot), one wrong note (red band + dot). Drawn by hand: decorative, so it's hidden from screen readers.
function SampleBar() {
  const bottom = 64
  const notes: { x: number; step: number; half?: boolean; lyric: string }[] = [
    { x: 70, step: -2, lyric: 'Twin' },
    { x: 114, step: -2, lyric: 'kle' },
    { x: 150, step: 2, lyric: 'twin' },
    { x: 196, step: 2, lyric: 'kle' },
    { x: 262, step: 3, lyric: 'lit' },
    { x: 308, step: 3, lyric: 'tle' },
    { x: 360, step: 2, half: true, lyric: 'star,' },
  ]
  const y = (step: number) => bottom - step * 5
  return (
    <svg className="welcome-svg" viewBox="0 0 420 106" aria-hidden="true">
      <rect x={56} y={bottom - 52} width={154} height={64} rx={6} fill="#1f9d55" opacity={0.1} />
      <rect x={248} y={bottom - 52} width={28} height={64} rx={6} fill="#d49b00" opacity={0.26} />
      <rect x={294} y={bottom - 52} width={28} height={64} rx={6} fill="#d6334a" opacity={0.26} />
      <circle cx={262} cy={bottom - 58} r={3} fill="#a87c00" />
      <circle cx={308} cy={bottom - 58} r={3} fill="#d6334a" />
      {[0, 1, 2, 3, 4].map((l) => (
        <line key={l} x1={14} x2={406} y1={bottom - l * 10} y2={bottom - l * 10} stroke="#3d3d3d" strokeWidth={1} />
      ))}
      <line x1={232} x2={232} y1={bottom - 40} y2={bottom} stroke="#3d3d3d" />
      <line x1={406} x2={406} y1={bottom - 40} y2={bottom} stroke="#3d3d3d" strokeWidth={2.5} />
      <text x={14} y={bottom + 8} fontFamily="Apple Symbols, Bravura, 'Noto Music', serif" fontSize={58}>
        𝄞
      </text>
      <text x={40} y={bottom - 22} fontFamily="Times New Roman, serif" fontWeight={700} fontSize={19}>
        4
      </text>
      <text x={40} y={bottom - 2} fontFamily="Times New Roman, serif" fontWeight={700} fontSize={19}>
        4
      </text>
      {[93, 173, 285].map((x) => (
        <text key={x} x={x} y={bottom + 34} textAnchor="middle" fontFamily="Times New Roman, serif" fontSize={15}>
          -
        </text>
      ))}
      {notes.map((n) => (
        <g key={n.x}>
          {n.step <= -2 && <line x1={n.x - 9} x2={n.x + 9} y1={bottom + 10} y2={bottom + 10} stroke="#3d3d3d" />}
          <ellipse
            cx={n.x}
            cy={y(n.step)}
            rx={6.3}
            ry={4.5}
            transform={`rotate(-20 ${n.x} ${y(n.step)})`}
            fill={n.half ? 'none' : '#111'}
            stroke="#111"
            strokeWidth={n.half ? 1.7 : 0}
          />
          <line x1={n.x + 5.7} x2={n.x + 5.7} y1={y(n.step) - 1} y2={y(n.step) - 32} stroke="#111" strokeWidth={1.3} />
          <text x={n.x} y={bottom + 34} textAnchor="middle" fontFamily="Times New Roman, serif" fontSize={15}>
            {n.lyric}
          </text>
        </g>
      ))}
    </svg>
  )
}
