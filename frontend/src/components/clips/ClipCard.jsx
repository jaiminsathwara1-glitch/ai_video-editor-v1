import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Film, Clock, Tag, AlertTriangle, Eye, CheckCircle, XCircle, Trash2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { clipsApi } from '@/api/clips'
import ScoreRing from '@/components/ui/ScoreRing'
import Badge from '@/components/ui/Badge'
import clsx from 'clsx'

function formatDuration(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(1)
  return m > 0 ? `${m}:${sec.padStart(4, '0')}` : `${sec}s`
}

export default function ClipCard({ clip, analysis, onSelect, selected }) {
  const [imgError, setImgError] = useState(false)
  const score = analysis?.overall_score ?? analysis?.score
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const confirmTimeoutRef = useRef(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
    }
  }, [])

  const handleDeleteDirect = async () => {
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
      await clipsApi.remove(clip.id)
      await queryClient.invalidateQueries({ queryKey: ['clips'] })
      toast.success('Clip successfully removed')
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || 'Unknown error'
      toast.error(`Failed to remove clip: ${errMsg}`)
      console.error(err)
    } finally {
      setIsDeleting(false)
      setConfirmDelete(false)
    }
  }

  const issues = [
    analysis?.is_blurry      && 'Blurry',
    analysis?.is_shaky       && 'Shaky',
    analysis?.is_overexposed && 'Overexposed',
    analysis?.is_underexposed&& 'Dark',
    analysis?.has_duplicate  && 'Duplicate',
  ].filter(Boolean)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ y: -2 }}
      onClick={() => onSelect?.(clip)}
      onMouseLeave={() => setConfirmDelete(false)}
      className={clsx(
        'panel p-0 overflow-hidden cursor-pointer group transition-all duration-200 relative',
        selected ? 'ring-2 ring-accent' : 'hover:border-white/20',
      )}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-editor-active overflow-hidden">
        {/* Hover Delete Button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            handleDeleteDirect()
          }}
          disabled={isDeleting}
          className={clsx(
            "absolute top-2 left-2 p-1.5 rounded transition-all duration-150 z-10",
            confirmDelete
              ? "bg-danger text-white scale-110 opacity-100 animate-pulse"
              : "bg-black/60 hover:bg-danger text-white/80 hover:text-white opacity-0 group-hover:opacity-100"
          )}
          title={confirmDelete ? "Click again to confirm deletion" : "Remove Clip"}
        >
          {confirmDelete ? (
            <span className="text-[9px] font-bold px-1 uppercase tracking-wider flex items-center gap-1">
              <Trash2 size={10} /> Confirm
            </span>
          ) : (
            <Trash2 size={13} />
          )}
        </button>
        {clip.thumbnail_path && !imgError ? (
          <img
            src={`/api/v1/clips/${clip.id}/thumbnail`}
            alt={clip.original_filename}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <Film size={28} className="text-white/15" />
          </div>
        )}

        {/* Score overlay */}
        <div className="absolute top-2 right-2">
          <ScoreRing score={score} size={40} strokeWidth={3.5} />
        </div>

        {/* Status overlay */}
        {clip.status !== 'analysed' && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
            <span className="text-xs text-white/60 font-medium capitalize">{clip.status}</span>
          </div>
        )}

        {/* Duration badge */}
        {clip.duration && (
          <div className="absolute bottom-2 left-2 bg-black/70 rounded px-1.5 py-0.5 text-2xs text-white font-mono">
            {formatDuration(clip.duration)}
          </div>
        )}

        {/* Resolution badge */}
        {clip.width && (
          <div className="absolute bottom-2 right-2 bg-black/70 rounded px-1.5 py-0.5 text-2xs text-white font-mono">
            {clip.width}×{clip.height}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-3 space-y-2">
        {/* Filename */}
        <p className="text-xs font-medium text-white truncate" title={clip.original_filename}>
          {clip.original_filename}
        </p>

        {/* Metadata row */}
        <div className="flex items-center gap-3 text-2xs text-white/40">
          <span className="flex items-center gap-1">
            <Clock size={10} /> {formatDuration(clip.duration)}
          </span>
          {clip.fps && <span>{clip.fps.toFixed(0)} fps</span>}
          {clip.video_codec && <span className="uppercase">{clip.video_codec}</span>}
        </div>

        {/* Issues */}
        {issues.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {issues.map((i) => (
              <Badge key={i} variant="warning">
                <AlertTriangle size={9} /> {i}
              </Badge>
            ))}
          </div>
        )}

        {/* Tags */}
        {analysis?.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {analysis.tags.slice(0, 4).map((tag) => (
              <Badge key={tag} variant="muted">
                <Tag size={9} /> {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Summary */}
        {analysis?.summary && (
          <p className="text-2xs text-white/35 line-clamp-2 leading-relaxed">
            {analysis.summary}
          </p>
        )}

        {/* Usable ranges */}
        {analysis?.usable_ranges?.length > 0 && (
          <div className="text-2xs text-white/30">
            <span className="text-success">{analysis.usable_ranges.length}</span> usable range{analysis.usable_ranges.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </motion.div>
  )
}
