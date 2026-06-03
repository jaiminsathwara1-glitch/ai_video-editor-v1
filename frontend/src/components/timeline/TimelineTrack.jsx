import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  horizontalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { useTimelineStore } from '@/stores/timelineStore'
import ClipBlock from './ClipBlock'
import { useQueries } from '@tanstack/react-query'
import { clipsApi } from '@/api/clips'

function TimeRuler({ totalDuration, zoom }) {
  const tickSpacing = 5   // seconds between ticks
  const ticks = Math.ceil(totalDuration / tickSpacing) + 1

  return (
    <div className="h-6 flex-shrink-0 relative border-b border-editor-border overflow-hidden">
      {Array.from({ length: ticks }).map((_, i) => {
        const secs = i * tickSpacing
        const left = secs * zoom * 100
        return (
          <div key={i} className="absolute top-0 flex flex-col items-center" style={{ left }}>
            <div className="w-px h-2 bg-editor-border" />
            <span className="text-2xs text-white/25 font-mono mt-0.5">{secs}s</span>
          </div>
        )
      })}
    </div>
  )
}

export default function TimelineTrack({ projectId, onSelectClip, selectedClipId }) {
  const { entries, reorder, zoom } = useTimelineStore()
  const totalDuration = entries.reduce((s, e) => s + (e.out_point - e.in_point), 0)

  // Load clip metadata for all entries in parallel
  const clipIds = [...new Set(entries.map(e => e.clip_id))]
  const clipQueries = useQueries({
    queries: clipIds.map(id => ({
      queryKey: ['clip', id],
      queryFn:  () => clipsApi.get(id),
      staleTime: 5 * 60 * 1000,
    })),
  })
  // Build a lookup map: clip_id -> metadata object
  const clipMetaMap = Object.fromEntries(
    clipIds.map((id, i) => [id, clipQueries[i]?.data ?? null])
  )

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  )

  function handleDragEnd(event) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const fromIdx = entries.findIndex(e => e.clip_id === active.id)
    const toIdx   = entries.findIndex(e => e.clip_id === over.id)
    reorder(fromIdx, toIdx)
  }

  if (!entries.length) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-white/30 border border-dashed border-editor-border rounded-lg">
        No timeline — generate one from the clips page
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <div style={{ minWidth: `${totalDuration * zoom * 100 + 120}px` }}>
        <TimeRuler totalDuration={totalDuration} zoom={zoom} />

        <div className="timeline-track relative">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={entries.map(e => e.clip_id)}
              strategy={horizontalListSortingStrategy}
            >
              <div className="flex gap-1 p-1 h-full items-center">
                {entries.map((entry) => (
                  <ClipBlock
                    key={entry.clip_id}
                    entry={entry}
                    clipMeta={clipMetaMap[entry.clip_id]}
                    zoom={zoom}
                    isSelected={selectedClipId === entry.clip_id}
                    onClick={() => onSelectClip?.(entry.clip_id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>
      </div>
    </div>
  )
}
