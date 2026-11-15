export function Welcome({ onStart }: { onStart: () => void }) {
  return (
    <main className="welcome">
      <p className="eyebrow">Welcome to</p>
      <h1 className="brand">Gensing</h1>
      <p className="lede">
        Your sheet music, marked up like a voice teacher would. Load a score, sing it through, and see every note
        colored: in tune, a little flat or sharp, a wrong note, early or late, skipped, or extra.
      </p>
      <ol className="steps">
        <li>
          <span>1</span>Choose a MusicXML score
        </li>
        <li>
          <span>2</span>Record yourself singing it
        </li>
        <li>
          <span>3</span>Get a colored score, a grade, and coaching tips
        </li>
      </ol>
      <button className="btn btn-primary btn-lg" onClick={onStart}>
        Get started
      </button>
    </main>
  )
}
