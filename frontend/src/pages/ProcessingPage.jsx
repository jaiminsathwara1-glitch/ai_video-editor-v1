import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Cpu, CheckCircle2, Clock, ChevronRight,
  RefreshCw, Zap, AlertCircle, Film,
  Activity, BarChart2, Layers, Play, Wifi, Trash2, AlertTriangle, Terminal
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { clipsApi } from '@/api/clips'
import client from '@/api/client'
import {
  useStartProjectAnalysis,
  useDetectDuplicates,
  useTaskStatus,
} from '@/hooks/useAnalysis'
import { useProjectSocket } from '@/hooks/useSocket'
import Button from '@/components/ui/Button'
import ProgressBar from '@/components/ui/ProgressBar'
import clsx from 'clsx'

const STATUS_DOT = {
  uploading:  'bg-white/20',
  uploaded:   'bg-warning animate-pulse',
  analysing:  'bg-accent animate-pulse',
  analysed:   'bg-success',
  error:      'bg-danger',
}

const STATUS_LABEL = {
  uploading:  { text: 'Uploading',   cls: 'text-white/30' },
  uploaded:   { text: 'Pending',     cls: 'text-warning' },
  analysing:  { text: 'Analysing',   cls: 'text-accent' },
  analysed:   { text: 'Done',        cls: 'text-success' },
  error:      { text: 'Error',       cls: 'text-danger' },
}

function getStageStates(clipStatus, taskStatus) {
  const stages = {
    frames: 'pending',
    blur: 'pending',
    exposure: 'pending',
    scene: 'pending',
    whisper: 'pending',
    ai: 'pending',
  }

  if (clipStatus === 'analysed') {
    return {
      frames: 'done',
      blur: 'done',
      exposure: 'done',
      scene: 'done',
      whisper: 'done',
      ai: 'done',
    }
  }

  if (clipStatus === 'error') {
    const step = taskStatus?.progress?.step ?? 'cv_analysis'
    if (step === 'cv_analysis') {
      return {
        frames: 'error',
        blur: 'pending',
        exposure: 'pending',
        scene: 'pending',
        whisper: 'pending',
        ai: 'pending',
      }
    } else if (step === 'scene_detection') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'error',
        whisper: 'pending',
        ai: 'pending',
      }
    } else if (step === 'transcription') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'done',
        whisper: 'error',
        ai: 'pending',
      }
    } else if (step === 'llm_tagging') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'done',
        whisper: 'done',
        ai: 'error',
      }
    }
    return {
      frames: 'error',
      blur: 'error',
      exposure: 'error',
      scene: 'error',
      whisper: 'error',
      ai: 'error',
    }
  }

  if (clipStatus === 'analysing') {
    const step = taskStatus?.progress?.step ?? 'cv_analysis'
    if (step === 'cv_analysis') {
      return {
        frames: 'active',
        blur: 'pending',
        exposure: 'pending',
        scene: 'pending',
        whisper: 'pending',
        ai: 'pending',
      }
    } else if (step === 'scene_detection') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'active',
        whisper: 'pending',
        ai: 'pending',
      }
    } else if (step === 'transcription') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'done',
        whisper: 'active',
        ai: 'pending',
      }
    } else if (step === 'llm_tagging') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'done',
        whisper: 'done',
        ai: 'active',
      }
    } else if (step === 'auto_trimming') {
      return {
        frames: 'done',
        blur: 'done',
        exposure: 'done',
        scene: 'done',
        whisper: 'done',
        ai: 'done',
      }
    }
  }

  return stages
}

function ClipStatusRow({ clip }) {
  const s = STATUS_LABEL[clip.status] ?? STATUS_LABEL.uploading
  const { data: taskStatus } = useTaskStatus(clip.analysis_task_id, {
    enabled: clip.status === 'analysing' || clip.status === 'error',
    refetchInterval: 3000,
  })

  const stageStates = getStageStates(clip.status, taskStatus)

  return (
    <div className="flex items-center gap-3 py-2 px-4 hover:bg-editor-hover transition-colors">
      <div className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', STATUS_DOT[clip.status] ?? 'bg-white/20')} />
      <span className="text-xs text-white/70 flex-1 truncate font-mono">{clip.original_filename}</span>
      
      {/* AI Pipeline Stages visualizer */}
      <div className="flex items-center gap-1.5 bg-editor-active/30 px-2 py-0.5 rounded-md border border-white/5 flex-shrink-0 mr-2">
        {PIPELINE_STAGES.map(({ icon, label, key }) => {
          const state = stageStates[key]
          return (
            <div
              key={key}
              title={`${label}: ${state}`}
              className={clsx(
                "w-5 h-5 rounded-full flex items-center justify-center text-xs transition-all duration-300",
                state === 'done'    && "bg-success/20 text-success border border-success/30",
                state === 'active'  && "bg-accent/20 text-accent border border-accent/40 animate-pulse scale-105",
                state === 'error'   && "bg-danger/25 text-danger border border-danger/45 animate-bounce",
                state === 'pending' && "bg-white/5 text-white/20 border border-white/5"
              )}
            >
              {icon}
            </div>
          )
        })}
      </div>

      {clip.duration && (
        <span className="text-2xs text-white/30 font-mono">{clip.duration.toFixed(1)}s</span>
      )}
      <span className={clsx('text-2xs font-medium', s.cls)}>{s.text}</span>
    </div>
  )
}

function StatBox({ label, value, color = 'text-white' }) {
  return (
    <div className="text-center px-4 py-3">
      <p className={clsx('text-2xl font-bold tabular-nums', color)}>{value}</p>
      <p className="text-2xs text-white/30 mt-0.5">{label}</p>
    </div>
  )
}

const PIPELINE_STAGES = [
  { icon: '🎥', label: 'Frame Extraction',     key: 'frames'    },
  { icon: '👁️', label: 'Blur & Shake',         key: 'blur'      },
  { icon: '☀️', label: 'Exposure Analysis',    key: 'exposure'  },
  { icon: '🎬', label: 'Scene Detection',      key: 'scene'     },
  { icon: '🎙️', label: 'Transcription',        key: 'whisper'   },
  { icon: '🤖', label: 'AI Tags & Scoring',    key: 'ai'        },
]

export default function ProcessingPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const { data: clips = [], isLoading, refetch } = useQuery({
    queryKey: ['clips', projectId],
    queryFn: () => clipsApi.list(projectId),
    refetchInterval: 4000,
    enabled: !!projectId,
  })

  // ── Worker health check — polls every 10 s ────────────────────────────────
  const { data: workerHealth } = useQuery({
    queryKey: ['health', 'workers'],
    queryFn: () => fetch('/health/workers').then(r => r.json()),
    refetchInterval: 10_000,
    retry: false,
  })
  const analysisWorkerDown = workerHealth && !workerHealth.analysis_worker_online

  const startAnalysis    = useStartProjectAnalysis()
  const detectDuplicates = useDetectDuplicates()
  const [analysisTaskId, setAnalysisTaskId] = useState(null)
  const { data: taskStatus } = useTaskStatus(analysisTaskId)

  // Real-time socket updates
  const { connected } = useProjectSocket(projectId, {
    onClipUpdate: () => refetch(),
    onAnalysisUpdate: () => refetch(),
  })

  const counts = {
    total:     clips.length,
    uploaded:  clips.filter(c => c.status === 'uploaded').length,
    analysing: clips.filter(c => c.status === 'analysing').length,
    analysed:  clips.filter(c => c.status === 'analysed').length,
    error:     clips.filter(c => c.status === 'error').length,
  }

  const analysedPct = counts.total > 0
    ? Math.round((counts.analysed / counts.total) * 100)
    : 0

  const isAnalysing = counts.analysing > 0 || (taskStatus && !['SUCCESS', 'FAILURE'].includes(taskStatus?.status))
  const pendingCount = counts.uploaded + counts.error + counts.analysing

  async function handleStartAnalysis() {
    if (analysisWorkerDown) {
      toast.error('Analysis worker is offline! Restart it first (see the red banner above).', { duration: 6000 })
      return
    }
    const result = await startAnalysis.mutateAsync(projectId)
    if (result?.task_id) setAnalysisTaskId(result.task_id)
  }

  return (
    <div className="p-6 max-w-4xl space-y-5">

      {/* ── Worker Offline Banner ── */}
      <AnimatePresence>
        {analysisWorkerDown && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10 }}
            className="rounded-xl border border-red-500/40 bg-red-500/10 p-4"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-red-300">
                  ⚠️ Analysis Worker is Offline — Analysis will not run!
                </p>
                <p className="text-xs text-red-400/80 mt-1">
                  The Celery analysis worker has stopped. Open a new terminal in the project folder and run:
                </p>
                <div className="mt-2 flex items-center gap-2 bg-black/40 rounded-lg px-3 py-2 border border-red-500/20">
                  <Terminal size={12} className="text-red-400 flex-shrink-0" />
                  <code className="text-xs text-red-200 font-mono break-all">
                    venv\Scripts\celery.exe -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -P threads -c 4
                  </code>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            AI Processing
            {isAnalysing && (
              <span className="text-xs font-normal text-accent border border-accent/30 bg-accent/10 px-2 py-0.5 rounded-full animate-pulse">
                Live
              </span>
            )}
          </h1>
          <p className="text-sm text-white/40 mt-0.5 flex items-center gap-2">
            <span>{counts.total} clips · {counts.analysed} analysed</span>
            <span className={clsx('flex items-center gap-1 text-2xs', connected ? 'text-success' : 'text-white/25')}>
              <Wifi size={9} />
              {connected ? 'Live' : 'Offline'}
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw size={12} /> Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleStartAnalysis}
            loading={startAnalysis.isPending}
            disabled={pendingCount === 0}
          >
            <Zap size={12} />
            Analyse {pendingCount > 0 ? `(${pendingCount})` : 'All'}
          </Button>
        </div>
      </motion.div>

      {/* ── Progress Overview ── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="panel overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-editor-border">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-white">Overall Progress</span>
            <span className="text-lg font-bold text-accent font-mono">{analysedPct}%</span>
          </div>
          <ProgressBar
            value={analysedPct}
            color={analysedPct === 100 ? 'success' : 'accent'}
            className="h-2"
          />
        </div>

        <div className="grid grid-cols-5 divide-x divide-editor-border">
          <StatBox label="Total"     value={counts.total}     color="text-white"   />
          <StatBox label="Pending"   value={counts.uploaded}  color="text-warning" />
          <StatBox label="Analysing" value={counts.analysing} color="text-accent"  />
          <StatBox label="Done"      value={counts.analysed}  color="text-success" />
          <StatBox label="Errors"    value={counts.error}     color={counts.error > 0 ? 'text-danger' : 'text-white/20'} />
        </div>
      </motion.div>

      {/* ── AI Pipeline stages ── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="panel p-4"
      >
        <p className="text-xs font-semibold text-white/50 uppercase tracking-widest mb-4">AI Pipeline Stages</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {PIPELINE_STAGES.map(({ icon, label, key }, idx) => {
            const done = counts.analysed > 0
            const active = isAnalysing && !done
            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className={clsx(
                  'flex items-center gap-2.5 p-2.5 rounded-lg border',
                  done   ? 'border-success/20 bg-success/5'  :
                  active ? 'border-accent/20  bg-accent/5'   :
                            'border-editor-border bg-editor-active'
                )}
              >
                <span className="text-base">{icon}</span>
                <span className="text-xs text-white/70 flex-1">{label}</span>
                {done ? (
                  <CheckCircle2 size={13} className="text-success flex-shrink-0" />
                ) : active ? (
                  <div className="w-3 h-3 rounded-full border-2 border-accent border-t-transparent animate-spin flex-shrink-0" />
                ) : (
                  <Clock size={13} className="text-white/20 flex-shrink-0" />
                )}
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* ── Clip list ── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="panel overflow-hidden"
      >
        <div className="px-4 py-3 border-b border-editor-border flex items-center justify-between">
          <p className="text-xs font-semibold text-white/60">
            Clip Status
            <span className="ml-2 text-white/30 font-normal">{clips.length} files</span>
          </p>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => navigate(`/project/${projectId}/clips`)}
            disabled={counts.analysed === 0}
          >
            Review Clips <ChevronRight size={11} />
          </Button>
        </div>
        <div className="max-h-72 overflow-y-auto divide-y divide-editor-border/30">
          {isLoading ? (
            <p className="text-center py-6 text-xs text-white/30">Loading clips…</p>
          ) : clips.length === 0 ? (
            <div className="py-8 text-center">
              <Film size={24} className="text-white/15 mx-auto mb-2" />
              <p className="text-xs text-white/30">No clips uploaded yet</p>
            </div>
          ) : (
            clips.map((clip) => <ClipStatusRow key={clip.id} clip={clip} />)
          )}
        </div>
      </motion.div>

      {/* ── CTAs ── */}
      <AnimatePresence>
        {counts.analysed > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3"
          >
            <Button
              variant="primary"
              onClick={() => navigate(`/project/${projectId}/clips`)}
            >
              Review {counts.analysed} Clips <ChevronRight size={14} />
            </Button>
            <Button
              variant="outline"
              onClick={() => detectDuplicates.mutate(projectId)}
              loading={detectDuplicates.isPending}
            >
              Detect Duplicates
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
