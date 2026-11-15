import type { ReactElement } from 'react'

// Pixel icons drawn from character grids, so they stay crisp at 1x and 2x and match the desktop's pixel type.
//   '#' = current text colour · 'y' = caution yellow · 'w' = white · '.' = transparent
const GRIDS = {
  play: [
    '...........',
    '..#........',
    '..###......',
    '..#####....',
    '..#######..',
    '..#########',
    '..#######..',
    '..#####....',
    '..###......',
    '..#........',
    '...........',
  ],
  pause: [
    '...........',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '..###.###..',
    '...........',
  ],
  note: [
    '................',
    '.......##.......',
    '.......###......',
    '.......####.....',
    '.......##.##....',
    '.......##..##...',
    '.......##...#...',
    '.......##...#...',
    '.......##.......',
    '...######.......',
    '..#######.......',
    '..#######.......',
    '..#######.......',
    '...#####........',
    '................',
    '................',
  ],
  caution: [
    '.......##.......',
    '......#yy#......',
    '......#yy#......',
    '.....#yyyy#.....',
    '.....#y##y#.....',
    '....#yy##yy#....',
    '....#yy##yy#....',
    '...#yyy##yyy#...',
    '...#yyy##yyy#...',
    '..#yyyy##yyyy#..',
    '..#yyyyyyyyyy#..',
    '.#yyyyy##yyyyy#.',
    '.#yyyyy##yyyyy#.',
    '#yyyyyyyyyyyyyy#',
    '################',
  ],
  check: [
    '.........#',
    '........##',
    '.......##.',
    '#.....##..',
    '##...##...',
    '.##.##....',
    '..###.....',
    '...#......',
  ],
} as const

export type IconName = keyof typeof GRIDS
const FILL: Record<string, string> = { '#': 'currentColor', y: '#F7D23E', w: '#FFFFFF' }

export function Icon({ name, size = 1, className }: { name: IconName; size?: number; className?: string }) {
  const grid = GRIDS[name]
  const w = grid[0].length
  const h = grid.length
  const rects: ReactElement[] = []
  grid.forEach((row, y) => {
    let x = 0
    while (x < w) {
      const c = row[x]
      let end = x + 1
      while (end < w && row[end] === c) end++
      if (c !== '.') rects.push(<rect key={`${x}-${y}`} x={x} y={y} width={end - x} height={1} fill={FILL[c]} />)
      x = end
    }
  })
  return (
    <svg
      className={`icon${className ? ` ${className}` : ''}`}
      width={w * size}
      height={h * size}
      viewBox={`0 0 ${w} ${h}`}
      shapeRendering="crispEdges"
      aria-hidden="true"
      focusable="false"
    >
      {rects}
    </svg>
  )
}
