import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, Film, Clock, Layers, Zap, ChevronRight,
  Trash2, FolderOpen, Activity, TrendingUp,
  Upload, Scissors, Download, BarChart2, Sparkles
} from 'lucide-react'
import { useProjects, useCreateProject, useDeleteProject } from '@/hooks/useProjects'
import { useProjectStore } from '@/stores/projectStore'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import clsx from 'clsx'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDuration(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

/** ── Animated gradient background orbs ── */
function BackgroundOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10">
      <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-accent/5 blur-3xl" />
      <div className="absolute top-1/3 -left-32 w-80 h-80 rounded-full bg-accent/3 blur-3xl" />
      <div className="absolute bottom-0 right-1/4 w-72 h-72 rounded-full bg-success/3 blur-3xl" />
    </div>
  )
}

/** ── Stat card ── */
function StatCard({ label, value, icon: Icon, color, suffix = '' }) {
  const cls = {
    accent:  { bg: 'bg-accent/10', border: 'border-accent/20', text: 'text-accent', icon: 'text-accent' },
    success: { bg: 'bg-success/10', border: 'border-success/20', text: 'text-success', icon: 'text-success' },
    warning: { bg: 'bg-warning/10', border: 'border-warning/20', text: 'text-warning', icon: 'text-warning' },
  }[color] ?? {}

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx('panel p-4 flex items-center gap-3 border', cls.border)}
    >
      <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', cls.bg)}>
        <Icon size={18} className={cls.icon} />
      </div>
      <div>
        <p className={clsx('text-2xl font-bold tabular-nums', cls.text)}>{value ?? '—'}{suffix}</p>
        <p className="text-xs text-white/40">{label}</p>
      </div>
    </motion.div>
  )
}

/** ── Create project modal ── */
function CreateProjectModal({ onClose }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const create = useCreateProject()

  const submit = (e) => {
    e.preventDefault()
    if (!name.trim()) return
    create.mutate({ name: name.trim(), description: desc.trim() })
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.93, y: 20, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.93, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel border-white/10 overflow-hidden">
          {/* Modal header gradient bar */}
          <div className="h-1 bg-gradient-to-r from-accent via-accent/80 to-transparent" />

          <div className="p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-9 h-9 rounded-xl bg-accent/15 border border-accent/20 flex items-center justify-center">
                <Sparkles size={16} className="text-accent" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-white">New Project</h2>
                <p className="text-xs text-white/40">Start a new rough-cut workflow</p>
              </div>
            </div>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">Project Name *</label>
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Wedding Highlights 2025"
                  className="w-full bg-editor-bg border border-editor-border rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:border-accent focus:outline-none transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">Description</label>
                <textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="Optional project notes..."
                  rows={3}
                  className="w-full bg-editor-bg border border-editor-border rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:border-accent focus:outline-none transition-colors resize-none"
                />
              </div>
              <div className="flex gap-2 justify-end pt-1">
                <Button variant="ghost" type="button" size="sm" onClick={onClose}>Cancel</Button>
                <Button variant="primary" type="submit" size="sm" disabled={!name.trim() || create.isPending}>
                  {create.isPending ? 'Creating…' : '✦ Create Project'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

/** ── Workflow step badge ── */
function WorkflowStep({ icon: Icon, label, step, color }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold border', color)}>
        <Icon size={14} />
      </div>
      <span className="text-2xs text-white/40 text-center leading-tight">{label}</span>
    </div>
  )
}

/** ── Project card ── */
function ProjectCard({ project, onDelete }) {
  const navigate = useNavigate()
  const { setCurrentProject, addRecent } = useProjectStore()

  const open = () => {
    setCurrentProject(project.id)
    addRecent({ id: project.id, name: project.name, createdAt: project.created_at })
    navigate(`/project/${project.id}/processing`)
  }

  const statusConfig = {
    created:    { label: 'Draft',       cls: 'text-white/40 bg-white/5 border-white/10' },
    analysing:  { label: 'Analysing',   cls: 'text-warning bg-warning/10 border-warning/25' },
    ready:      { label: 'Ready',       cls: 'text-success bg-success/10 border-success/25' },
    processing: { label: 'Processing',  cls: 'text-accent  bg-accent/10  border-accent/25'  },
    exported:   { label: 'Exported',    cls: 'text-success bg-success/10 border-success/25' },
    error:      { label: 'Error',       cls: 'text-danger  bg-danger/10  border-danger/25'  },
  }
  const status = statusConfig[project.status] ?? statusConfig.created

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      whileHover={{ y: -2 }}
      className="panel group overflow-hidden cursor-pointer hover:border-white/15 transition-all duration-200"
      onClick={open}
    >
      {/* Color accent strip */}
      <div className="h-0.5 bg-gradient-to-r from-accent/70 via-accent/30 to-transparent" />

      {/* Thumbnail placeholder */}
      <div className="h-24 bg-editor-active relative overflow-hidden">
        {/* Grid overlay decoration */}
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'linear-gradient(rgba(79,142,247,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(79,142,247,0.5) 1px, transparent 1px)',
            backgroundSize: '20px 20px'
          }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <Film size={28} className="text-white/10" />
        </div>
        {/* Clip count overlay */}
        {project.clip_count > 0 && (
          <div className="absolute bottom-2 left-2 flex items-center gap-1 bg-black/60 rounded px-1.5 py-0.5">
            <Film size={9} className="text-white/50" />
            <span className="text-2xs text-white/50 font-mono">{project.clip_count} clips</span>
          </div>
        )}
        {/* Status badge */}
        <div className="absolute top-2 right-2">
          <span className={clsx('text-2xs font-medium px-1.5 py-0.5 rounded border', status.cls)}>
            {status.label}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="p-3.5">
        <h3 className="font-semibold text-white text-sm leading-tight truncate mb-1">{project.name}</h3>
        {project.description && (
          <p className="text-xs text-white/35 line-clamp-2 mb-2">{project.description}</p>
        )}

        <div className="flex items-center gap-3 text-2xs text-white/30 mb-3">
          <span className="flex items-center gap-1"><Clock size={9} /> {formatDate(project.created_at)}</span>
          {project.total_duration > 0 && (
            <span className="flex items-center gap-1"><Activity size={9} /> {formatDuration(project.total_duration)}</span>
          )}
        </div>

        <div className="flex gap-1.5">
          <button
            onClick={(e) => { e.stopPropagation(); open() }}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-accent/10 hover:bg-accent/20 border border-accent/20 hover:border-accent/35 text-accent text-xs rounded-lg transition-all"
          >
            <ChevronRight size={11} />
            Open
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(project.id) }}
            className="p-1.5 hover:bg-danger/10 border border-transparent hover:border-danger/25 text-white/20 hover:text-danger rounded-lg transition-all"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </motion.div>
  )
}

/** ── Main Page ── */
export default function HomePage() {
  const [showCreate, setShowCreate] = useState(false)
  const { data: projects = [], isLoading } = useProjects()
  const deleteProject = useDeleteProject()

  const totalClips     = projects.reduce((s, p) => s + (p.clip_count ?? 0), 0)
  const activeCount    = projects.filter((p) => ['analysing', 'processing', 'ready'].includes(p.status)).length
  const totalDuration  = projects.reduce((s, p) => s + (p.total_duration ?? 0), 0)

  return (
    <div className="min-h-full">
      <BackgroundOrbs />

      <div className="p-6 max-w-6xl mx-auto space-y-8">
        {/* ── Header ── */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Projects
              {projects.length > 0 && (
                <span className="ml-2 text-sm font-normal text-white/30">({projects.length})</span>
              )}
            </h1>
            <p className="text-sm text-white/40 mt-1">
              AI-powered 4K rough-cut editing workspace
            </p>
          </div>
          <Button
            id="create-project-btn"
            variant="primary"
            size="md"
            onClick={() => setShowCreate(true)}
          >
            <Plus size={14} />
            New Project
          </Button>
        </motion.div>

        {/* ── Stats ── */}
        {(projects.length > 0 || !isLoading) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Total Projects"   value={projects.length}           icon={Layers}    color="accent" />
            <StatCard label="Total Clips"      value={totalClips}                icon={Film}      color="success" />
            <StatCard label="Total Duration"   value={formatDuration(totalDuration)} icon={Clock} color="warning" />
          </div>
        )}

        {/* ── Workflow guide (only when no projects) ── */}
        {!isLoading && projects.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel border-dashed border-white/10 p-8"
          >
            {/* Steps */}
            <div className="flex items-center justify-center gap-2 mb-8">
              {[
                { icon: Upload,   label: 'Upload Clips',      color: 'bg-accent/10 border-accent/30 text-accent'   },
                { icon: Zap,      label: 'AI Analysis',       color: 'bg-warning/10 border-warning/30 text-warning' },
                { icon: Scissors, label: 'Review Timeline',   color: 'bg-success/10 border-success/30 text-success' },
                { icon: Download, label: 'Export to Premiere',color: 'bg-accent/10 border-accent/30 text-accent'   },
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <WorkflowStep {...step} />
                  {i < 3 && (
                    <div className="w-8 h-px bg-gradient-to-r from-white/20 to-white/5" />
                  )}
                </div>
              ))}
            </div>

            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mx-auto mb-4">
                <Film size={26} className="text-accent/60" />
              </div>
              <p className="text-white font-semibold mb-1">No projects yet</p>
              <p className="text-sm text-white/40 mb-5">
                Create your first project to start AI-assisted rough cutting of 4K video clips
              </p>
              <Button variant="primary" onClick={() => setShowCreate(true)}>
                <Plus size={14} /> Create First Project
              </Button>
            </div>
          </motion.div>
        )}

        {/* ── Projects grid ── */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="panel h-56 animate-pulse" />
            ))}
          </div>
        ) : projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            <AnimatePresence>
              {projects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onDelete={(id) => deleteProject.mutate(id)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* ── Create modal ── */}
      <AnimatePresence>
        {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} />}
      </AnimatePresence>
    </div>
  )
}
