import { useState, useRef } from 'react'
import { useTimelineStore } from '@/stores/timelineStore'
import { Scissors } from 'lucide-react'

/**
 * Visual trim handle for a selected clip entry.
 * Shows in/out points as draggable handles on a waveform-style bar.
 */
export default function TrimHandle({ entry }) {
  const setTrim = useTimelineStore((s) => s.setTrim)
  const [localIn,  setLocalIn]  = useState(entry.in_point)
  const [localOut, setLocalOut] = useState(entry.out_point)
  const totalDuration = entry.out_point - entry.in_point || 1
  const clipDuration  = entry.out_point  // approximate total clip length

  const barRef = useRef(null)

  function handleMouseDown(side) {
    return (e) => {
      e.preventDefault()
      const bar = barRef.current
      if (!bar) return
      const { left, width } = bar.getBoundingClientRect()

      function onMove(ev) {
        const ratio = Math.max(0, Math.min(1, (ev.clientX - left) / width))
        const time  = ratio * clipDuration

        if (side === 'in') {
          const newIn = Math.min(time, localOut - 0.5)
          setLocalIn(Math.max(0, newIn))
        } else {
          const newOut = Math.max(time, localIn + 0.5)
          setLocalOut(Math.min(clipDuration, newOut))
        }
      }

      function onUp() {
        setTrim(entry.clip_id, localIn, localOut)
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }

      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    }
  }

  const inPct  = (localIn  / (clipDuration || 1)) * 100
  const outPct = (localOut / (clipDuration || 1)) * 100

  return (
    <div className="p-4 bg-editor-panel border border-editor-border rounded-lg">
      <div className="flex items-center gap-2 mb-3">
        <Scissors size={13} className="text-accent" />
        <span className="text-xs font-medium text-white">Trim</span>
        <span className="ml-auto text-2xs font-mono text-white/40">
          {localIn.toFixed(2)}s → {localOut.toFixed(2)}s
          <span className="ml-2 text-accent">({(localOut - localIn).toFixed(2)}s)</span>
        </span>
      </div>

      {/* Bar */}
      <div ref={barRef} className="relative h-8 bg-editor-active rounded overflow-visible select-none">
        {/* Trimmed region (highlighted) */}
        <div
          className="absolute top-0 h-full bg-accent/20 border-x border-accent"
          style={{ left: `${inPct}%`, width: `${outPct - inPct}%` }}
        />

        {/* In handle */}
        <div
          onMouseDown={handleMouseDown('in')}
          className="absolute top-0 bottom-0 w-3 -ml-1.5 bg-accent cursor-ew-resize rounded-l flex items-center justify-center z-10"
          style={{ left: `${inPct}%` }}
        >
          <div className="w-px h-4 bg-white/50" />
        </div>

        {/* Out handle */}
        <div
          onMouseDown={handleMouseDown('out')}
          className="absolute top-0 bottom-0 w-3 -mr-1.5 bg-accent cursor-ew-resize rounded-r flex items-center justify-center z-10"
          style={{ left: `${outPct}%`, transform: 'translateX(-100%)' }}
        >
          <div className="w-px h-4 bg-white/50" />
        </div>

        {/* Waveform placeholder */}
        <div className="absolute inset-0 flex items-center gap-px px-2 opacity-20">
          {Array.from({ length: 60 }).map((_, i) => (
            <div
              key={i}
              className="flex-1 bg-white rounded-full"
              style={{ height: `${20 + Math.sin(i * 0.8) * 15 + Math.random() * 10}%` }}
            />
          ))}
        </div>
      </div>

      <div className="flex justify-between mt-2 text-2xs text-white/30 font-mono">
        <span>0.00s</span>
        <span>{clipDuration.toFixed(2)}s</span>
      </div>
    </div>
  )
}
