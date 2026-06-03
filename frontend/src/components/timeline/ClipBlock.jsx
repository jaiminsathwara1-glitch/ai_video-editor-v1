import { useRef, useState, useCallback } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  Lock, Unlock, Check, X, GripVertical, Scissors,
  AlertTriangle
} from 'lucide-react'
import { useTimelineStore } from '@/stores/timelineStore'
import clsx from 'clsx'

const scoreColor = (score) => {
  if (!score) return 'bg-white/10'
  if (score >= 7) return 'bg-success/80'
  if (score >= 4) return 'bg-warning/80'
  return 'bg-danger/80'
}

const MIN_WIDTH_PX = 40  // minimum clip width regardless of zoom

export default function ClipBlock({ entry, clipMeta, zoom, isSelected, onClick }) {
  const { approve, reject, toggleLock, setTrim, removeEntry } = useTimelineStore()
  const duration = entry.out_point - entry.in_point
  const widthPx  = Math.max(MIN_WIDTH_PX, duration * zoom * 100)

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: entry.clip_id, disabled: entry.locked })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    width: `${widthPx}px`,
    minWidth: `${MIN_WIDTH_PX}px`,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      className={clsx(
        'relative h-14 rounded clip-block flex-shrink-0 overflow-hidden group',
        'border border-transparent transition-all duration-150',
        entry.rejected  ? 'opacity-40 grayscale' : '',
        entry.approved  ? 'ring-1 ring-success'  : '',
        entry.locked    ? 'ring-1 ring-white/20 cursor-default' : '',
        isSelected      ? 'ring-2 ring-accent' : 'hover:ring-1 hover:ring-white/30',
        scoreColor(entry.score),
      )}
    >
      {/* Thumbnail bg */}
      {clipMeta?.thumbnail_path && (
        <img
          src={`/api/v1/clips/${entry.clip_id}/thumbnail`}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
      )}

      {/* Drag handle */}
      {!entry.locked && (
        <div
          {...attributes}
          {...listeners}
          className="absolute left-0 top-0 bottom-0 w-5 flex items-center justify-center
                     opacity-0 group-hover:opacity-100 transition-opacity cursor-grab
                     bg-gradient-to-r from-black/50 to-transparent"
        >
          <GripVertical size={12} className="text-white/70" />
        </div>
      )}

      {/* Content */}
      <div className="absolute inset-0 flex flex-col justify-between p-1.5 pl-5">
        <div className="flex items-center gap-1">
          <span
            className="text-2xs font-mono text-white/80 truncate flex-1"
            title={clipMeta?.original_filename ?? entry.clip_id}
          >
            {clipMeta?.original_filename ?? `${entry.clip_id.slice(0, 8)}…`}
          </span>
          {entry.score != null && (
            <span className="text-2xs font-bold text-white/90 flex-shrink-0">
              {entry.score.toFixed(1)}
            </span>
          )}
        </div>
        <div className="text-2xs font-mono text-white/50">
          {entry.in_point.toFixed(1)}s → {entry.out_point.toFixed(1)}s
        </div>
      </div>

      {/* Action bar (hover) */}
      <div className="absolute top-0 right-0 flex opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.stopPropagation(); approve(entry.clip_id) }}
          className="p-0.5 bg-black/60 hover:text-success text-white/50"
          title="Approve"
        >
          <Check size={10} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); reject(entry.clip_id) }}
          className="p-0.5 bg-black/60 hover:text-danger text-white/50"
          title="Reject"
        >
          <X size={10} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); toggleLock(entry.clip_id) }}
          className="p-0.5 bg-black/60 hover:text-white text-white/50"
          title={entry.locked ? 'Unlock' : 'Lock'}
        >
          {entry.locked ? <Lock size={10} /> : <Unlock size={10} />}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); removeEntry(entry.clip_id) }}
          className="p-0.5 bg-black/60 hover:text-danger text-white/50"
          title="Remove"
        >
          <X size={10} />
        </button>
      </div>

      {/* Rejected overlay */}
      {entry.rejected && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
          <X size={18} className="text-danger" />
        </div>
      )}

      {/* Lock indicator */}
      {entry.locked && (
        <div className="absolute bottom-1 left-1">
          <Lock size={9} className="text-white/40" />
        </div>
      )}
    </div>
  )
}
