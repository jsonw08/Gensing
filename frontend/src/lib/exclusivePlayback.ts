// One recording plays at a time: whatever starts playing claims the output, and whatever was playing
// before is stopped (the take player and a clicked note's snippet never overlap; neither do two players).

let current: { stop: () => void } | null = null

/** Call when something starts playing; `stop` is how to silence it when something else starts.
 *  Returns a release function to call when it stops on its own (so it isn't "stopped" later by mistake). */
export function claimPlayback(stop: () => void): () => void {
  const mine = { stop }
  const previous = current
  current = mine
  if (previous) previous.stop()
  return () => {
    if (current === mine) current = null
  }
}
