import { motion, AnimatePresence } from 'framer-motion'
import { Film, X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { useUploadStore } from '@/stores/uploadStore'
import ProgressBar from '@/components/ui/ProgressBar'
import clsx from 'clsx'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

const statusIcon = {
  queued:    <Loader2 size={13} className="text-white/30" />,
  uploading: <Loader2 size={13} className="animate-spin text-accent" />,
  done:      <CheckCircle2 size={13} className="text-success" />,
  error:     <AlertCircle  size={13} className="text-danger" />,
}

function FileRow({ entry }) {
  const remove = useUploadStore((s) => s.remove)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{    opacity: 0, y: -4, scale: 0.98 }}
      className={clsx(
        'flex items-center gap-3 p-3 rounded-lg border',
        entry.status === 'error'
          ? 'border-danger/30 bg-danger/5'
          : 'border-editor-border bg-editor-panel',
      )}
    >
      {/* Icon */}
      <div className="w-8 h-8 rounded bg-editor-active flex items-center justify-center flex-shrink-0">
        <Film size={14} className="text-white/40" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-white font-medium truncate">{entry.file.name}</span>
          <span className="text-2xs text-white/30 flex-shrink-0">
            {formatBytes(entry.file.size)}
          </span>
          {statusIcon[entry.status]}
        </div>

        {entry.status === 'uploading' && (
          <div className="flex items-center gap-2">
            <ProgressBar value={entry.progress} showLabel className="flex-1" />
            <span className="text-2xs text-white/30 font-mono flex-shrink-0">
              {entry.chunksDone}/{entry.chunksTotal} chunks
            </span>
          </div>
        )}

        {entry.status === 'done' && (
          <p className="text-2xs text-success">
            Upload complete — Clip ID: {entry.clipId?.slice(0, 8)}…
          </p>
        )}

        {entry.status === 'error' && (
          <p className="text-2xs text-danger truncate">{entry.error}</p>
        )}

        {entry.status === 'queued' && (
          <p className="text-2xs text-white/30">Queued</p>
        )}
      </div>

      {/* Remove */}
      {entry.status !== 'uploading' && (
        <button
          onClick={() => remove(entry.id)}
          className="p-1 rounded hover:bg-editor-hover text-white/30 hover:text-white/70 transition-colors"
        >
          <X size={12} />
        </button>
      )}
    </motion.div>
  )
}

export default function FileQueue() {
  const uploads = useUploadStore((s) => s.uploads)

  if (!uploads.length) return null

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-medium text-white/60">
          Upload Queue ({uploads.length} file{uploads.length !== 1 ? 's' : ''})
        </h3>
        <span className="text-2xs text-white/30">
          {uploads.filter(u => u.status === 'done').length} done
        </span>
      </div>
      <AnimatePresence>
        {uploads.map((entry) => (
          <FileRow key={entry.id} entry={entry} />
        ))}
      </AnimatePresence>
    </div>
  )
}
