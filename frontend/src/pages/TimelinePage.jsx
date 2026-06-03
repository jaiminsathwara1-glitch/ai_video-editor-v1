import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Scissors, ZoomIn, ZoomOut, RefreshCw, Check, X,
  Lock, ChevronRight, Play, RotateCcw, Save,
  Info, Layers, Clock, Star, Filter, Unlock, Sparkles
} from 'lucide-react'
import { useTimelines, useGenerateTimeline, useReorderTimeline } from '@/hooks/useTimelines'
import { useQuery } from '@tanstack/react-query'
import { clipsApi } from '@/api/clips'
import { useTimelineStore } from '@/stores/timelineStore'
import TimelineTrack from '@/components/timeline/TimelineTrack'
import TrimHandle from '@/components/timeline/TrimHandle'
import Button from '@/components/ui/Button'
import ProgressBar from '@/components/ui/ProgressBar'
import clsx from 'clsx'

function LabeledStat({ label, value, color = 'text-white/80' }) {
  return (
    <div className="flex justify-between items-center py-1.5">
      <span className="text-xs text-white/40">{label}</span>
      <span className={clsx('text-xs font-mono font-semibold', color)}>{value}</span>
    </div>
  )
}

export default function TimelinePage() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const { data: timelines = [] } = useTimelines(projectId)
  const generateTimeline = useGenerateTimeline()
  const reorderTimeline  = useReorderTimeline()
  const currentTimeline  = timelines[0]

  const {
    entries, selectedEntryId, selectEntry,
    zoom, setZoom, isDirty, approve, reject, toggleLock,
    removeEntry, markSaved, timelineId,
  } = useTimelineStore()

  const [minScore, setMinScore]           = useState(3)
  const [targetDuration, setTargetDuration] = useState('')

  const selectedEntry = entries.find(e => e.clip_id === selectedEntryId)

  // Fetch metadata for selected clip to show its filename
  const { data: selectedClipMeta } = useQuery({
    queryKey: ['clip', selectedEntryId],
    queryFn:  () => clipsApi.get(selectedEntryId),
    enabled:  !!selectedEntryId,
    staleTime: 5 * 60 * 1000,
  })

  const totalDuration = entries.reduce((s, e) => s + (e.out_point - e.in_point), 0)
  const approvedCount = entries.filter(e => e.approved).length
  const rejectedCount = entries.filter(e => e.rejected).length
  const lockedCount   = entries.filter(e => e.locked).length
  const approvedPct   = entries.length ? Math.round((approvedCount / entries.length) * 100) : 0

  async function handleGenerate() {
    await generateTimeline.mutateAsync({
      project_id:      projectId,
      name:            'Rough Cut',
      min_score:       minScore,
      target_duration: targetDuration ? Number(targetDuration) : null,
    })
  }

  function formatDuration(s) {
    const m = Math.floor(s / 60)
    const sec = (s % 60).toFixed(1)
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Global toolbar ── */}
      <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2.5 border-b border-editor-border bg-editor-surface">
        <Scissors size={14} className="text-accent" />
        <span className="text-sm font-bold text-white">Timeline Editor</span>

        {isDirty && (
          <motion.span
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-2xs text-warning border border-warning/30 bg-warning/8 px-2 py-0.5 rounded-full"
          >
            • Unsaved
          </motion.span>
        )}

        {entries.length > 0 && (
          <span className="text-2xs text-white/30 hidden md:block">
            {entries.length} clips · {formatDuration(totalDuration)}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          {/* Zoom controls */}
          <div className="flex items-center bg-editor-active border border-editor-border rounded-md overflow-hidden">
            <button
              onClick={() => setZoom(zoom * 0.75)}
              className="p-1.5 hover:bg-editor-hover text-white/50 hover:text-white transition-colors"
            >
              <ZoomOut size={12} />
            </button>
            <span className="text-2xs font-mono text-white/40 px-2 min-w-[40px] text-center select-none">
              {(zoom * 100).toFixed(0)}%
            </span>
            <button
              onClick={() => setZoom(zoom * 1.33)}
              className="p-1.5 hover:bg-editor-hover text-white/50 hover:text-white transition-colors"
            >
              <ZoomIn size={12} />
            </button>
          </div>

          <div className="w-px h-4 bg-editor-border" />

          <Button size="sm" variant="outline" onClick={handleGenerate} loading={generateTimeline.isPending}>
            <RefreshCw size={11} /> Regenerate
          </Button>

          {entries.length > 0 && (
            <Button
              id="ai-reorder-btn"
              size="sm"
              variant="outline"
              onClick={() => currentTimeline?.id && reorderTimeline.mutate(currentTimeline.id)}
              loading={reorderTimeline.isPending}
              title="Ask Groq AI to suggest the best order for your clips"
              className="border-accent/40 text-accent hover:bg-accent/10"
            >
              <Sparkles size={11} /> AI Reorder
            </Button>
          )}

          <Button size="sm" variant="primary" onClick={() => navigate(`/project/${projectId}/export`)}>
            Export <ChevronRight size={11} />
          </Button>
        </div>
      </div>

      {/* ── 3-column layout ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left sidebar — settings */}
        <div className="w-56 flex-shrink-0 border-r border-editor-border bg-editor-surface flex flex-col overflow-y-auto">

          {/* Generate settings */}
          <div className="p-4 border-b border-editor-border space-y-4">
            <p className="text-2xs font-semibold text-white/40 uppercase tracking-widest">Generate Settings</p>

            <div>
              <div className="flex justify-between text-xs mb-2">
                <span className="text-white/50">Min Score</span>
                <span className="text-accent font-mono font-bold">{minScore.toFixed(1)}</span>
              </div>
              <input
                type="range" min="0" max="10" step="0.5"
                value={minScore}
                onChange={e => setMinScore(Number(e.target.value))}
                className="w-full accent-accent h-1.5"
              />
              <div className="flex justify-between text-2xs text-white/20 mt-1">
                <span>All</span><span>Best only</span>
              </div>
            </div>

            <div>
              <label className="text-xs text-white/50 block mb-1.5">Target Duration (s)</label>
              <input
                type="number"
                placeholder="No limit"
                value={targetDuration}
                onChange={e => setTargetDuration(e.target.value)}
                className="w-full bg-editor-active border border-editor-border rounded-md px-2.5 py-1.5 text-xs text-white placeholder-white/25 focus:outline-none focus:border-accent"
              />
            </div>

            <Button size="sm" className="w-full" onClick={handleGenerate} loading={generateTimeline.isPending}>
              <RefreshCw size={11} /> Generate
            </Button>
          </div>

          {/* Timeline stats */}
          <div className="p-4 border-b border-editor-border space-y-1">
            <p className="text-2xs font-semibold text-white/40 uppercase tracking-widest mb-3">Stats</p>
            <LabeledStat label="Clips"     value={entries.length}            />
            <LabeledStat label="Duration"  value={formatDuration(totalDuration)} />
            <LabeledStat label="Approved"  value={approvedCount} color="text-success" />
            <LabeledStat label="Rejected"  value={rejectedCount} color={rejectedCount > 0 ? 'text-danger' : 'text-white/20'} />
            <LabeledStat label="Locked"    value={lockedCount}   color={lockedCount   > 0 ? 'text-warning' : 'text-white/20'} />

            {entries.length > 0 && (
              <div className="pt-2">
                <div className="flex justify-between text-2xs mb-1 text-white/40">
                  <span>Review progress</span>
                  <span>{approvedPct}%</span>
                </div>
                <ProgressBar value={approvedPct} color={approvedPct === 100 ? 'success' : 'accent'} />
              </div>
            )}
          </div>

          {/* Selected clip actions */}
          <AnimatePresence>
            {selectedEntry && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="p-4 space-y-3"
              >
                <p className="text-2xs font-semibold text-white/40 uppercase tracking-widest">Selected Clip</p>

                <div className="space-y-1 text-xs">
                  <div className="text-white/80 text-2xs truncate font-medium" title={selectedClipMeta?.original_filename ?? selectedEntry.clip_id}>
                    {selectedClipMeta?.original_filename ?? `${selectedEntry.clip_id.slice(0, 12)}…`}
                  </div>
                  <div className="text-white/40">
                    In: <span className="font-mono text-white/70">{selectedEntry.in_point.toFixed(2)}s</span>
                    {' '}&nbsp;Out: <span className="font-mono text-white/70">{selectedEntry.out_point.toFixed(2)}s</span>
                  </div>
                  {selectedEntry.score != null && (
                    <div className="text-white/40">
                      Score: <span className={clsx('font-mono font-bold',
                        selectedEntry.score >= 7 ? 'text-success' :
                        selectedEntry.score >= 4 ? 'text-warning' : 'text-danger'
                      )}>{selectedEntry.score.toFixed(1)}</span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  <Button
                    size="xs"
                    variant={selectedEntry.approved ? 'success' : 'ghost'}
                    className={clsx('w-full', selectedEntry.approved && 'opacity-70')}
                    onClick={() => approve(selectedEntry.clip_id)}
                  >
                    <Check size={10} /> Approve
                  </Button>
                  <Button
                    size="xs"
                    variant={selectedEntry.rejected ? 'danger' : 'ghost'}
                    className={clsx('w-full', selectedEntry.rejected && 'opacity-70')}
                    onClick={() => reject(selectedEntry.clip_id)}
                  >
                    <X size={10} /> Reject
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    className="w-full"
                    onClick={() => toggleLock(selectedEntry.clip_id)}
                  >
                    {selectedEntry.locked ? <Unlock size={10} /> : <Lock size={10} />}
                    {selectedEntry.locked ? 'Unlock' : 'Lock'}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    className="w-full text-danger/80 hover:text-danger"
                    onClick={() => removeEntry(selectedEntry.clip_id)}
                  >
                    <X size={10} /> Remove
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ── Timeline area ── */}
        <div className="flex-1 overflow-hidden flex flex-col bg-editor-bg">

          {entries.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-5 text-center p-8">
              <div className="w-16 h-16 rounded-2xl bg-editor-panel border border-editor-border flex items-center justify-center">
                <Scissors size={26} className="text-white/20" />
              </div>
              <div>
                <p className="text-white font-semibold mb-1">No timeline generated yet</p>
                <p className="text-sm text-white/40 mb-4">
                  Configure the settings in the sidebar and generate a rough cut from your analysed clips
                </p>
              </div>
              <Button variant="primary" onClick={handleGenerate} loading={generateTimeline.isPending}>
                <RefreshCw size={14} /> Generate Rough Cut
              </Button>
              <p className="text-xs text-white/25">
                Tip: clips with score ≥ {minScore} will be included
              </p>
            </div>
          ) : (
            <>
              {/* Track header */}
              <div className="flex-shrink-0 flex items-center gap-2 px-4 py-2 border-b border-editor-border bg-editor-surface">
                <div className="w-8 text-2xs text-white/30 text-center font-medium">V1</div>
                <div className="flex-1 text-2xs text-white/20">
                  Video Track · {entries.length} clips · {formatDuration(totalDuration)}
                </div>
                {isDirty && (
                  <button
                    onClick={markSaved}
                    className="text-2xs text-white/40 hover:text-white/70 transition-colors flex items-center gap-1"
                  >
                    <Save size={10} /> Mark saved
                  </button>
                )}
              </div>

              {/* Scrollable timeline */}
              <div className="flex-1 overflow-auto p-4">
                <TimelineTrack
                  projectId={projectId}
                  onSelectClip={selectEntry}
                  selectedClipId={selectedEntryId}
                />
              </div>

              {/* Trim panel */}
              <AnimatePresence>
                {selectedEntry && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="flex-shrink-0 border-t border-editor-border bg-editor-surface overflow-hidden"
                  >
                    <div className="p-4">
                      <TrimHandle entry={selectedEntry} />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
