import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Film, Clock, Mic, Tag, Eye, AlertTriangle,
  BarChart2, Scissors, ChevronRight, Trash2
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { clipsApi } from '@/api/clips'
import ScoreRing from '@/components/ui/ScoreRing'
import Badge from '@/components/ui/Badge'
import ProgressBar from '@/components/ui/ProgressBar'
import { useClipAnalysis } from '@/hooks/useAnalysis'
import clsx from 'clsx'

function MetricRow({ label, value, pct }) {
  return (
    <div>
      <div className="flex justify-between text-2xs mb-1">
        <span className="text-white/40">{label}</span>
        <span className="font-mono text-white/80">{value?.toFixed(1) ?? '—'}</span>
      </div>
      <ProgressBar value={pct} color={pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'} />
    </div>
  )
}

export default function ClipDetail({ clip, onClose }) {
  const { data: analysis, isLoading } = useClipAnalysis(clip?.id)
  const [tab, setTab] = useState('overview')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const confirmTimeoutRef = useRef(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
    }
  }, [])

  if (!clip) return null

  const handleDelete = async () => {
    console.log("Delete button clicked. Clip object:", clip)
    if (!confirmDelete) {
      setConfirmDelete(true)
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
      confirmTimeoutRef.current = setTimeout(() => {
        setConfirmDelete(false)
      }, 4000)
      return
    }

    if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
    setIsDeleting(true)
    try {
      console.log("Sending delete request for clip id:", clip.id)
      const res = await clipsApi.remove(clip.id)
      console.log("Delete response received:", res)
      
      console.log("Invalidating queries starting with ['clips']")
      await queryClient.invalidateQueries({ queryKey: ['clips'] })
      
      toast.success('Clip successfully removed')
      onClose()
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || 'Unknown error'
      console.error("Deletion failed:", err)
      toast.error(`Failed to delete clip: ${errMsg}`)
    } finally {
      setIsDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: 20, opacity: 0 }}
        animate={{ x: 0,  opacity: 1 }}
        exit={{   x: 20,  opacity: 0 }}
        className="w-80 flex-shrink-0 panel rounded-none border-r-0 border-t-0 border-b-0 flex flex-col h-full overflow-hidden border-l border-editor-border"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-editor-border flex-shrink-0">
          <div className="flex items-center gap-2">
            <Film size={14} className="text-white/40" />
            <span className="text-xs font-medium text-white truncate max-w-[150px]">
              {clip.original_filename}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className={clsx(
                "p-1 rounded transition-colors",
                confirmDelete 
                  ? "bg-danger text-white animate-pulse" 
                  : "hover:bg-danger/20 text-danger/80 hover:text-danger"
              )}
              title={confirmDelete ? "Click again to confirm" : "Remove Clip"}
            >
              <Trash2 size={13} />
            </button>
            <button onClick={onClose} className="p-1 hover:bg-editor-hover rounded text-white/30 hover:text-white/70">
              <X size={13} />
            </button>
          </div>
        </div>
        <div className="aspect-video bg-editor-active flex-shrink-0 relative">
          {clip.trimmed_file_path ? (
            <video
              src={`/api/v1/clips/${clip.id}/trimmed`}
              poster={`/api/v1/clips/${clip.id}/thumbnail`}
              controls
              className="w-full h-full object-contain"
            />
          ) : (
            <img
              src={`/api/v1/clips/${clip.id}/thumbnail`}
              alt=""
              className="w-full h-full object-cover"
              onError={(e) => { e.target.style.display = 'none' }}
            />
          )}
        </div>

        {/* Score */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-editor-border flex-shrink-0">
          <ScoreRing score={analysis?.overall_score} size={52} />
          <div>
            <p className="text-lg font-bold text-white">
              {analysis?.overall_score?.toFixed(1) ?? '—'}<span className="text-white/30 text-sm">/10</span>
            </p>
            <p className="text-2xs text-white/40">Overall Quality</p>
            <div className="flex gap-1 mt-1 flex-wrap">
              {analysis?.is_blurry      && <Badge variant="warning">Blurry</Badge>}
              {analysis?.is_shaky       && <Badge variant="warning">Shaky</Badge>}
              {analysis?.is_overexposed && <Badge variant="warning">Overexposed</Badge>}
              {analysis?.has_duplicate  && <Badge variant="danger">Duplicate</Badge>}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-editor-border flex-shrink-0">
          {['overview', 'transcript', 'scenes'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-xs font-medium capitalize transition-colors
                ${tab === t ? 'text-accent border-b-2 border-accent' : 'text-white/40 hover:text-white/70'}`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {tab === 'overview' && (
            <>
              {/* Clip metadata */}
              <div className="space-y-1.5">
                <p className="text-2xs text-white/30 uppercase tracking-wider mb-2">Metadata</p>
                {[
                  ['Duration', clip.duration ? `${clip.duration.toFixed(2)}s` : '—'],
                  ['Resolution', clip.width ? `${clip.width}×${clip.height}` : '—'],
                  ['FPS', clip.fps?.toFixed(2)],
                  ['Codec', clip.video_codec],
                  ['Audio', clip.audio_codec],
                ].map(([k, v]) => v && (
                  <div key={k} className="flex justify-between text-xs">
                    <span className="text-white/40">{k}</span>
                    <span className="font-mono text-white/70">{v}</span>
                  </div>
                ))}
              </div>

              {/* Quality metrics */}
              {analysis && (
                <div className="space-y-3">
                  <p className="text-2xs text-white/30 uppercase tracking-wider">Quality Metrics</p>
                  <MetricRow label="Sharpness" value={analysis.blur_score}     pct={(analysis.blur_score ?? 0) * 10} />
                  <MetricRow label="Stability" value={analysis.shake_score}    pct={(analysis.shake_score ?? 0) * 10} />
                  <MetricRow label="Exposure"  value={analysis.exposure_score} pct={(analysis.exposure_score ?? 0) * 10} />
                </div>
              )}

              {/* Usable ranges */}
              {analysis?.usable_ranges?.length > 0 && (
                <div>
                  <p className="text-2xs text-white/30 uppercase tracking-wider mb-2">Usable Ranges</p>
                  <div className="space-y-1.5">
                    {analysis.usable_ranges.map((r, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-success/10 border border-success/20 rounded px-2 py-1.5">
                        <Scissors size={10} className="text-success" />
                        <span className="font-mono text-success">
                          {r.start.toFixed(2)}s → {r.end.toFixed(2)}s
                        </span>
                        <span className="ml-auto text-white/40">
                          {(r.end - r.start).toFixed(2)}s
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tags */}
              {analysis?.tags?.length > 0 && (
                <div>
                  <p className="text-2xs text-white/30 uppercase tracking-wider mb-2">AI Tags</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.tags.map((t) => (
                      <Badge key={t} variant="accent">
                        <Tag size={9} /> {t}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary */}
              {analysis?.summary && (
                <div>
                  <p className="text-2xs text-white/30 uppercase tracking-wider mb-2">AI Summary</p>
                  <p className="text-xs text-white/60 leading-relaxed">{analysis.summary}</p>
                </div>
              )}
            </>
          )}

          {tab === 'transcript' && (
            <div>
              {analysis?.transcript ? (
                <>
                  <p className="text-xs text-white/60 leading-relaxed whitespace-pre-wrap">
                    {analysis.transcript}
                  </p>
                  {analysis.transcript_segments?.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="text-2xs text-white/30 uppercase tracking-wider">Segments</p>
                      {analysis.transcript_segments.map((seg, i) => (
                        <div key={i} className="text-xs border-l-2 border-accent/30 pl-2">
                          <span className="font-mono text-white/30">
                            {seg.start.toFixed(1)}s
                          </span>
                          <span className="ml-2 text-white/70">{seg.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-xs text-white/30 italic">No transcript available</p>
              )}
            </div>
          )}

          {tab === 'scenes' && (
            <div className="space-y-2">
              {analysis?.scenes?.length > 0 ? (
                analysis.scenes.map((scene) => (
                  <div key={scene.scene_number} className="surface p-2.5 text-xs">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-white/40">Scene {scene.scene_number}</span>
                      <span className="ml-auto text-white/30 font-mono">
                        {scene.duration.toFixed(2)}s
                      </span>
                    </div>
                    <div className="text-2xs font-mono text-white/40">
                      {scene.start_time.toFixed(2)}s → {scene.end_time.toFixed(2)}s
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-white/30 italic">No scenes detected</p>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-3 border-t border-editor-border bg-editor-surface flex gap-2 flex-shrink-0">
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className={clsx(
              "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border transition-all text-xs font-semibold disabled:opacity-50",
              confirmDelete 
                ? "bg-danger text-white border-danger animate-pulse" 
                : "border-danger/30 bg-danger/10 text-danger hover:bg-danger/20"
            )}
          >
            <Trash2 size={13} />
            {isDeleting ? 'Removing...' : confirmDelete ? 'Click again to Confirm' : 'Remove Clip'}
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
