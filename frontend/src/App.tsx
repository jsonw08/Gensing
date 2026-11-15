import { useState } from 'react'
import { type Take, useTakes } from './hooks/useTakes'
import { Evaluate } from './pages/Evaluate'
import { Practice, type Score } from './pages/Practice'
import { Welcome } from './pages/Welcome'

type Screen = { name: 'welcome' } | { name: 'practice' } | { name: 'evaluate'; take: Take }

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'welcome' })
  // Kept here (not in Practice) so they survive moving between pages.
  const [score, setScore] = useState<Score | null>(null)
  const takes = useTakes()

  switch (screen.name) {
    case 'welcome':
      return <Welcome onStart={() => setScreen({ name: 'practice' })} />
    case 'practice':
      return (
        <Practice
          score={score}
          onScoreChange={setScore}
          takes={takes}
          onEvaluate={(take) => setScreen({ name: 'evaluate', take })}
          onBack={() => setScreen({ name: 'welcome' })}
        />
      )
    case 'evaluate':
      return (
        <Evaluate
          take={screen.take}
          onBack={() => setScreen({ name: 'practice' })}
          onHome={() => setScreen({ name: 'welcome' })}
        />
      )
  }
}
