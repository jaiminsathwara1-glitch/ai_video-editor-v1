import { NavLink, useNavigate, useParams, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Film, Upload, Cpu, LayoutGrid, Scissors,
  Download, Zap, ChevronRight
} from 'lucide-react'
import { useProjectSocket } from '@/hooks/useSocket'
import { useProject } from '@/hooks/useProjects'
import clsx from 'clsx'

const globalLinks = [
  { to: '/', icon: LayoutGrid, label: 'Projects', end: true },
]

function NavItem({ to, icon: Icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-2.5 px-3 mx-2 py-2 text-sm rounded-lg transition-all duration-150',
          isActive
            ? 'bg-accent/15 text-accent font-medium border border-accent/20'
            : 'text-white/50 hover:text-white hover:bg-editor-hover',
        )
      }
    >
      <Icon size={15} />
      <span className="truncate">{label}</span>
    </NavLink>
  )
}

function ProjectNav({ projectId }) {
  const base = `/project/${projectId}`
  const links = [
    { to: `/upload?project=${projectId}`, icon: Upload,   label: 'Upload Clips' },
    { to: `${base}/processing`,           icon: Cpu,      label: 'Processing'   },
    { to: `${base}/clips`,                icon: Film,     label: 'Clip Review'  },
    { to: `${base}/timeline`,             icon: Scissors, label: 'Timeline'     },
    { to: `${base}/export`,               icon: Download, label: 'Export'       },
  ]

  const { data: project } = useProject(projectId)
  const { connected } = useProjectSocket(projectId)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-1"
    >
      {/* Project label */}
      <div className="px-4 pt-3 pb-1.5 flex items-center justify-between">
        <p className="text-2xs text-white/30 uppercase tracking-widest font-semibold">Current Project</p>
        <div
          className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'bg-success' : 'bg-white/20')}
          title={connected ? 'Live connection' : 'Disconnected'}
        />
      </div>

      {/* Project name */}
      {project && (
        <div className="px-4 pb-2">
          <p className="text-xs font-semibold text-white/80 truncate">{project.name}</p>
        </div>
      )}

      <nav className="space-y-0.5">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2.5 px-3 mx-2 py-2 text-sm rounded-lg transition-all duration-150',
                isActive
                  ? 'bg-accent/15 text-accent font-medium border border-accent/20'
                  : 'text-white/50 hover:text-white hover:bg-editor-hover',
              )
            }
          >
            <Icon size={14} />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>
    </motion.div>
  )
}

export default function Sidebar() {
  const { projectId } = useParams()

  return (
    <aside className="w-52 flex-shrink-0 bg-editor-surface border-r border-editor-border flex flex-col">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-editor-border">
        <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center flex-shrink-0 shadow-lg shadow-accent/20">
          <Zap size={14} className="text-white" />
        </div>
        <div className="min-w-0">
          <span className="font-bold tracking-tight text-white text-sm">CutAI</span>
          <span className="ml-2 text-2xs text-white/25 font-mono">v1.0</span>
        </div>
      </div>

      {/* Global nav */}
      <nav className="mt-2 space-y-0.5">
        {globalLinks.map(({ to, icon, label, end }) => (
          <NavItem key={to} to={to} icon={icon} label={label} end={end} />
        ))}
      </nav>

      {/* Divider */}
      {projectId && <div className="mx-4 my-2 h-px bg-editor-border" />}

      {/* Project-specific nav */}
      {projectId && <ProjectNav projectId={projectId} />}

      {/* Footer */}
      <div className="mt-auto p-4 border-t border-editor-border">
        <div className="text-2xs text-white/20 space-y-0.5">
          <p>API: <span className="font-mono">localhost:8000</span></p>
          <p className="text-white/15">CutAI Rough-Cut Platform</p>
        </div>
      </div>
    </aside>
  )
}
