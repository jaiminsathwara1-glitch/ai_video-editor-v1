import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, ChevronRight, Zap, CheckCircle2,
  Clock, Film, HardDrive, Cpu, Sparkles
} from 'lucide-react'
import { useUploadStore } from '@/stores/uploadStore'
import { useProjectStore } from '@/stores/projectStore'
import DropZone from '@/components/upload/DropZone'
import FileQueue from '@/components/upload/FileQueue'
import Button from '@/components/ui/Button'
import ProgressBar from '@/components/ui/ProgressBar'
import { useProjects, useCreateProject } from '@/hooks/useProjects'

function formatBytes(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function UploadStat({ label, value, icon: Icon, color = 'text-white/60' }) {
  return (
    <div className="flex flex-col items-center gap-1 py-3 px-4 rounded-lg bg-editor-panel border border-editor-border">
      <Icon size={14} className={color} />
      <p className="text-lg font-bold text-white tabular-nums">{value}</p>
      <p className="text-2xs text-white/40">{label}</p>
    </div>
  )
}

export default function UploadPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { currentProjectId, setCurrentProject, clearCurrent } = useProjectStore()

  // Server is the source of truth for projects
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects()
  const createProject = useCreateProject()

  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  const { enqueue, startAll, isUploading, uploads, setProject, doneCount } = useUploadStore()

  // Prefer ?project= URL param, then persisted store value
  const paramId    = params.get('project')
  const resolvedId = paramId || currentProjectId

  // Once loaded, if the stored ID is not in the server list → it is stale, clear it
  useEffect(() => {
    if (!isLoadingProjects && resolvedId) {
      const exists = projects.some(p => p.id === resolvedId)
      if (!exists) clearCurrent()
    }
  }, [isLoadingProjects, projects, resolvedId, clearCurrent])

  // Only treat as active if the server confirms the project exists
  const activeProjectId = (!isLoadingProjects && projects.some(p => p.id === resolvedId))
    ? resolvedId
    : null
  const activeProject = projects.find(p => p.id === activeProjectId) ?? null

  useEffect(() => {
    if (activeProjectId) setProject(activeProjectId)
  }, [activeProjectId, setProject])

  const queued     = uploads.filter(u => u.status === 'queued').length
  const total      = uploads.length
  const totalSize  = uploads.reduce((s, u) => s + (u.file?.size ?? 0), 0)
  const overallPct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  function handleStart() {
    startAll().then(() => {
      setTimeout(() => navigate(`/project/${activeProjectId}/processing`), 800)
    })
  }

  function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    createProject.mutate({ name: name.trim(), description: desc.trim() })
  }

  // ── Loading state ─────────────────────────────────────────────────────────────
  if (isLoadingProjects) {
    return (
      <div className="p-6 max-w-xl mx-auto mt-20 text-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-sm text-white/40">Loading…</p>
      </div>
    )
  }

  // ── Gate: no valid project → must create one first ────────────────────────────
  if (!activeProjectId) {
    return (
      <div className="p-6 max-w-md mx-auto mt-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel border-white/10 overflow-hidden"
        >
          {/* Accent top bar */}
          <div className="h-1 bg-gradient-to-r from-accent via-accent/70 to-transparent" />

          <div className="p-8 space-y-6">
            {/* Icon + title */}
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-accent/15 border border-accent/20 flex items-center justify-center flex-shrink-0">
                <Sparkles size={20} className="text-accent" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white">Create a Project First</h1>
                <p className="text-xs text-white/40 mt-0.5">
                  A project is required before you can upload video clips
                </p>
              </div>
            </div>

            {/* Workflow steps hint */}
            <div className="flex items-center gap-2 text-2xs text-white/25 select-none">
              {['Create Project', 'Upload Clips', 'AI Analysis', 'Export'].map((step, i, arr) => (
                <span key={step} className="flex items-center gap-2">
                  <span className={i === 0 ? 'text-accent font-semibold' : ''}>{step}</span>
                  {i < arr.length - 1 && <ChevronRight size={10} />}
                </span>
              ))}
            </div>

            {/* Create form */}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">
                  Project Name <span className="text-accent">*</span>
                </label>
                <input
                  autoFocus
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Wedding Highlights 2026"
                  required
                  className="w-full bg-editor-bg border border-editor-border rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:border-accent focus:outline-none transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">
                  Description <span className="text-white/20">(optional)</span>
                </label>
                <textarea
                  value={desc}
                  onChange={e => setDesc(e.target.value)}
                  placeholder="Project notes…"
                  rows={3}
                  className="w-full bg-editor-bg border border-editor-border rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:border-accent focus:outline-none transition-colors resize-none"
                />
              </div>
              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => navigate('/')}
                  className="text-xs text-white/30 hover:text-white/60 transition-colors"
                >
                  ← Back to Projects
                </button>
                <Button
                  variant="primary"
                  type="submit"
                  disabled={!name.trim() || createProject.isPending}
                >
                  {createProject.isPending ? 'Creating…' : '✦ Create & Start Uploading'}
                </Button>
              </div>
            </form>
          </div>
        </motion.div>
      </div>
    )
  }

  // ── Upload UI (only reachable once a valid project is confirmed) ──────────────
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Upload Clips</h1>
            <p className="text-sm text-white/40 mt-0.5">
              Project: <span className="text-accent">{activeProject?.name}</span>
            </p>
          </div>
          {doneCount > 0 && !isUploading && (
            <Button variant="primary" size="sm"
              onClick={() => navigate(`/project/${activeProjectId}/processing`)}>
              Go to Processing <ChevronRight size={13} />
            </Button>
          )}
        </div>
      </motion.div>

      {/* Drop zone */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <DropZone onFiles={enqueue} disabled={isUploading} />
      </motion.div>

      {/* Overall progress */}
      <AnimatePresence>
        {isUploading && (
          <motion.div
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="panel p-4 space-y-2"
          >
            <div className="flex items-center justify-between text-xs">
              <span className="text-white/60 flex items-center gap-1.5">
                <Cpu size={12} className="animate-pulse text-accent" />
                Uploading in progress…
              </span>
              <span className="text-accent font-mono font-bold">{overallPct}%</span>
            </div>
            <ProgressBar value={overallPct} color="accent" className="h-1.5" />
            <p className="text-2xs text-white/30">
              {doneCount} of {total} files complete — do not close this window
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stats */}
      {total > 0 && (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-4 gap-3">
          <UploadStat label="Total Files" value={total}                  icon={Film}         color="text-white/60" />
          <UploadStat label="Queued"      value={queued}                 icon={Clock}        color="text-white/40" />
          <UploadStat label="Done"        value={doneCount}              icon={CheckCircle2} color="text-success"  />
          <UploadStat label="Total Size"  value={formatBytes(totalSize)} icon={HardDrive}    color="text-white/60" />
        </motion.div>
      )}

      {/* File queue */}
      <FileQueue />

      {/* Action buttons */}
      {total > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3">
          <Button id="start-upload-btn" variant="primary" size="lg"
            onClick={handleStart} loading={isUploading}
            disabled={queued === 0 && !isUploading}>
            {isUploading
              ? <>Uploading {doneCount}/{total}…</>
              : <><Play size={14} /> Start Upload ({queued} files)</>}
          </Button>
          {doneCount > 0 && !isUploading && (
            <Button variant="outline" size="lg"
              onClick={() => navigate(`/project/${activeProjectId}/processing`)}>
              Continue to Processing <ChevronRight size={14} />
            </Button>
          )}
        </motion.div>
      )}

      {/* Tips */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
        className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 rounded bg-accent/15 flex items-center justify-center">
            <Zap size={12} className="text-accent" />
          </div>
          <p className="text-xs font-semibold text-white/70">Upload Tips</p>
        </div>
        <ul className="space-y-1.5">
          {[
            'Files are uploaded in 10 MB chunks — safe to close and resume later',
            'Support for MP4, MOV, AVI, MKV — 4K60 clips work best',
            'Metadata (codec, fps, resolution) is extracted automatically after upload',
            'Thumbnails are generated during the processing stage',
            'AI analysis runs in parallel — start as soon as first clips are uploaded',
          ].map((tip, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-white/40">
              <span className="text-accent/60 mt-0.5 flex-shrink-0">·</span>
              {tip}
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  )
}
