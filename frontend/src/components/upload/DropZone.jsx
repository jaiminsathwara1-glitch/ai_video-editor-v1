import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Film, Plus } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'

const ACCEPTED = {
  'video/mp4':       ['.mp4'],
  'video/quicktime': ['.mov'],
  'video/x-msvideo': ['.avi'],
  'video/x-matroska': ['.mkv'],
  'video/webm':      ['.webm'],
}

export default function DropZone({ onFiles, disabled }) {
  const onDrop = useCallback((accepted) => {
    if (accepted.length) onFiles(accepted)
  }, [onFiles])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    disabled,
    multiple: true,
  })

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer',
        'transition-all duration-300 select-none overflow-hidden',
        isDragActive && !isDragReject && 'dropzone-active border-accent',
        isDragReject  && 'border-danger bg-danger/5',
        !isDragActive && !isDragReject && 'border-editor-border hover:border-white/25 hover:bg-editor-hover/40',
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      <input {...getInputProps()} />

      {/* Background grid decoration */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: 'linear-gradient(rgba(79,142,247,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(79,142,247,0.06) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <AnimatePresence mode="wait">
        {isDragActive ? (
          <motion.div
            key="active"
            initial={{ scale: 0.88, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.88, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 22 }}
            className="relative flex flex-col items-center gap-3"
          >
            <motion.div
              animate={{ y: [0, -6, 0] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
              className="w-16 h-16 rounded-2xl bg-accent/20 border border-accent/30 flex items-center justify-center"
            >
              <Upload size={26} className="text-accent" />
            </motion.div>
            <p className="text-accent font-semibold text-lg">
              {isDragReject ? '✗ Unsupported format' : '↓ Drop to add clips'}
            </p>
            {!isDragReject && (
              <p className="text-xs text-accent/60">Release to queue {'{count}'} files</p>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="relative flex flex-col items-center gap-4"
          >
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-editor-panel border border-editor-border flex items-center justify-center">
                <Film size={26} className="text-white/25" />
              </div>
              <div className="absolute -bottom-1.5 -right-1.5 w-6 h-6 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center">
                <Plus size={12} className="text-accent" />
              </div>
            </div>

            <div>
              <p className="text-white font-semibold text-base mb-1">
                Drag & drop video clips here
              </p>
              <p className="text-sm text-white/40">
                or <span className="text-accent">click to browse</span>
                <span className="text-white/25"> — MP4, MOV, AVI, MKV, WebM</span>
              </p>
              <p className="text-xs text-white/20 mt-2">
                Optimised for 4K60 · 10 MB chunked upload · Up to 300 files
              </p>
            </div>

            {/* Format badges */}
            <div className="flex items-center gap-1.5 flex-wrap justify-center">
              {['MP4', 'MOV', 'AVI', 'MKV', 'WebM'].map((fmt) => (
                <span
                  key={fmt}
                  className="text-2xs px-2 py-0.5 rounded-full border border-editor-border text-white/30 bg-editor-active"
                >
                  {fmt}
                </span>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
