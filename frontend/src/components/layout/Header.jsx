import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Loader2, FolderOpen, ChevronRight, Upload,
  Cpu, Film, Scissors, Download, Home
} from 'lucide-react'
import { useProject } from '@/hooks/useProjects'
import { useUploadStore } from '@/stores/uploadStore'
import clsx from 'clsx'

const BREADCRUMBS = {
  '/':            { label: 'Projects',    icon: Home },
  '/upload':      { label: 'Upload',      icon: Upload },
  'processing':   { label: 'Processing',  icon: Cpu },
  'clips':        { label: 'Clip Review', icon: Film },
  'timeline':     { label: 'Timeline',    icon: Scissors },
  'export':       { label: 'Export',      icon: Download },
}

function CurrentPage({ location }) {
  const lastSegment = location.pathname.split('/').pop()
  const entry = BREADCRUMBS[lastSegment] ?? BREADCRUMBS[location.pathname]
  if (!entry) return null
  const { label, icon: Icon } = entry
  return (
    <span className="flex items-center gap-1.5 text-white font-medium">
      {Icon && <Icon size={12} className="text-white/50" />}
      {label}
    </span>
  )
}

export default function Header() {
  const { projectId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { data: project, isLoading } = useProject(projectId)
  const isUploading = useUploadStore(s => s.isUploading)
  const uploadDone  = useUploadStore(s => s.doneCount)
  const uploadTotal = useUploadStore(s => s.uploads.length)

  const statusColors = {
    created:   'bg-white/10 text-white/40',
    analysing: 'bg-warning/15 text-warning',
    ready:     'bg-success/15 text-success',
    error:     'bg-danger/15 text-danger',
    exported:  'bg-accent/15 text-accent',
  }

  return (
    <header className="h-11 flex-shrink-0 flex items-center px-5 bg-editor-surface border-b border-editor-border gap-2">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm min-w-0 flex-1">
        <button
          onClick={() => navigate('/')}
          className="text-white/30 hover:text-white/60 transition-colors flex-shrink-0"
        >
          <FolderOpen size={13} />
        </button>

        {isLoading ? (
          <Loader2 size={11} className="animate-spin text-white/25" />
        ) : project ? (
          <>
            <ChevronRight size={11} className="text-white/20 flex-shrink-0" />
            <button
              onClick={() => navigate(`/project/${projectId}/processing`)}
              className="text-white/50 hover:text-white/80 transition-colors text-xs truncate max-w-[120px]"
            >
              {project.name}
            </button>
            {project.status && (
              <span className={clsx('text-2xs px-1.5 py-0.5 rounded font-medium flex-shrink-0', statusColors[project.status])}>
                {project.status}
              </span>
            )}
            <ChevronRight size={11} className="text-white/15 flex-shrink-0" />
            <CurrentPage location={location} />
          </>
        ) : (
          <>
            <ChevronRight size={11} className="text-white/20 flex-shrink-0" />
            <CurrentPage location={location} />
          </>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Upload progress */}
        {isUploading && (
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-1.5 text-xs text-accent bg-accent/10 border border-accent/20 rounded-full px-2.5 py-1"
          >
            <Loader2 size={11} className="animate-spin" />
            <span>{uploadDone}/{uploadTotal} uploading</span>
          </motion.div>
        )}

        {/* API status dot */}
        <div
          className="w-2 h-2 rounded-full bg-success shadow-[0_0_4px_theme(colors.success.DEFAULT)]"
          title="API connected"
        />
      </div>
    </header>
  )
}
