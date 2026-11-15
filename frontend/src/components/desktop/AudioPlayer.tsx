import { useRef, useState } from 'react'
import { Icon } from './Icon'

function clock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '0:00'
  const s = Math.floor(sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// Play / pause, a position slider and the time, in the desktop's own controls (the browser's
// <audio controls> doesn't match anything). `durationSec` covers recordings whose length the browser
// can't read from the file (MediaRecorder WebM often reports Infinity).
export function AudioPlayer({ src, durationSec, label = 'Recording' }: { src: string; durationSec?: number; label?: string }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [fileDuration, setFileDuration] = useState(0)
  const duration = Number.isFinite(fileDuration) && fileDuration > 0 ? fileDuration : (durationSec ?? 0)

  const toggle = () => {
    const a = audioRef.current
    if (!a) return
    if (a.paused) a.play().catch(() => setPlaying(false))
    else a.pause()
  }

  return (
    <div className="player">
      <button type="button" className="button icon-button" onClick={toggle} aria-label={playing ? `Pause ${label}` : `Play ${label}`}>
        <Icon name={playing ? 'pause' : 'play'} />
      </button>
      <input
        type="range"
        className="slider"
        min={0}
        max={duration || 1}
        step={0.05}
        value={Math.min(time, duration || 1)}
        aria-label={`${label} position`}
        onChange={(e) => {
          const a = audioRef.current
          if (a) a.currentTime = Number(e.target.value)
          setTime(Number(e.target.value))
        }}
      />
      <span className="player-time">
        {clock(time)} / {clock(duration)}
      </span>
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(e) => setFileDuration(e.currentTarget.duration)}
        onDurationChange={(e) => setFileDuration(e.currentTarget.duration)}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
    </div>
  )
}
