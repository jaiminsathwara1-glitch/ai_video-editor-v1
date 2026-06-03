import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Download, FileCode, FileText, Film,
  CheckCircle2, Clock, Loader2, ChevronRight,
  Layers, Scissors, Code
} from 'lucide-react'
import {
  useTimelines, useExportTimeline, useDownloadTimeline,
  useRenderTimelineVideo, useDownloadTimelineVideo
} from '@/hooks/useTimelines'
import { useTaskStatus } from '@/hooks/useAnalysis'
import { useTimelineStore } from '@/stores/timelineStore'
import Button from '@/components/ui/Button'
import { useState } from 'react'
import clsx from 'clsx'

function formatDuration(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

function ExportCard({ id, title, description, icon: Icon, accentColor, borderColor, bgColor, onExport, onDownload, available, exporting }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'relative panel overflow-hidden hover:border-white/15 transition-all duration-200 group',
      )}
    >
      {/* Color strip */}
      <div className={clsx('absolute left-0 top-0 bottom-0 w-1', accentColor)} />

      <div className="pl-5 pr-4 py-4">
        <div className="flex items-start gap-3">
          <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', bgColor)}>
            <Icon size={18} className={accentColor.replace('bg-', 'text-').replace('/80', '')} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <p className="text-sm font-semibold text-white">{title}</p>
              {available && (
                <span className="text-2xs text-success border border-success/30 bg-success/10 px-1.5 py-0.5 rounded-full font-medium">
                  Ready
                </span>
              )}
            </div>
            <p className="text-xs text-white/40">{description}</p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <Button
            id={`export-${id}-btn`}
            size="sm"
            variant="outline"
            onClick={onExport}
            loading={exporting}
          >
            <FileCode size={11} /> Generate
          </Button>
          {available && (
            <Button
              id={`download-${id}-btn`}
              size="sm"
              variant="primary"
              onClick={onDownload}
            >
              <Download size={11} /> Download
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default function ExportPage() {
  const { projectId } = useParams()
  const { data: timelines = [] } = useTimelines(projectId)
  const timeline = timelines[0]

  const exportTimeline   = useExportTimeline()
  const downloadTimeline = useDownloadTimeline()
  const renderTimelineVideo = useRenderTimelineVideo()
  const downloadTimelineVideo = useDownloadTimelineVideo()

  const [exportTaskId, setExportTaskId] = useState(null)
  const { data: taskStatus } = useTaskStatus(exportTaskId)

  const { entries, timelineId } = useTimelineStore()
  const totalDuration = entries.reduce((s, e) => s + (e.out_point - e.in_point), 0)
  const approvedCount = entries.filter(e => e.approved).length

  async function handleExport(formats) {
    if (!timeline?.id) return
    const result = await exportTimeline.mutateAsync({ id: timeline.id, formats })
    if (result?.task_id) setExportTaskId(result.task_id)
  }

  const isExporting = exportTaskId && !['SUCCESS', 'FAILURE'].includes(taskStatus?.status)

  const EXPORT_FORMATS = [
    {
      id: 'video',
      title: 'Compiled Rough-Cut Video (MP4)',
      description: 'Render and download a compiled MP4 video from all the clips in your timeline',
      icon: Film,
      accentColor: 'bg-accent/80',
      borderColor: 'border-accent/20',
      bgColor: 'bg-accent/10',
      onExport: () => {
        if (timeline?.id) {
          renderTimelineVideo.mutate(
            { id: timeline.id },
            {
              onSuccess: (data) => {
                if (data?.task_id) setExportTaskId(data.task_id)
              }
            }
          )
        }
      },
      onDownload: () => {
        if (timeline?.id) {
          window.location.href = `/api/v1/timelines/${timeline.id}/download/video`
        }
      },
      available: !!timeline?.render_video_path,
      exporting: renderTimelineVideo.isPending,
    },
    {
      id: 'xml',
      title: 'Adobe Premiere XML',
      description: 'FCP XML format — fully compatible with Premiere Pro sequences',
      icon: FileCode,
      accentColor: 'bg-purple-500/80',
      borderColor: 'border-purple-500/20',
      bgColor: 'bg-purple-500/10',
      formats: ['xml'],
      available: !!timeline?.xml_export_path,
      fmt: 'xml',
    },
    {
      id: 'edl',
      title: 'EDL (CMX 3600)',
      description: 'Edit Decision List — compatible with DaVinci Resolve, Avid, Final Cut',
      icon: FileText,
      accentColor: 'bg-warning/80',
      borderColor: 'border-warning/20',
      bgColor: 'bg-warning/10',
      formats: ['edl'],
      available: !!timeline?.edl_export_path,
      fmt: 'edl',
    },
    {
      id: 'otio',
      title: 'OpenTimelineIO',
      description: 'Open interchange standard — works with any OTIO-compatible NLE',
      icon: Code,
      accentColor: 'bg-success/80',
      borderColor: 'border-success/20',
      bgColor: 'bg-success/10',
      formats: ['otio'],
      available: !!timeline?.otio_export_path,
      fmt: 'otio',
    },
    {
      id: 'json',
      title: 'Timeline JSON',
      description: 'Raw timeline data — useful for integrations and custom processing',
      icon: FileCode,
      accentColor: 'bg-white/20',
      borderColor: 'border-white/10',
      bgColor: 'bg-white/5',
      formats: ['json'],
      available: !!timeline?.id,
      fmt: 'json',
    },
  ]

  return (
    <div className="p-6 max-w-3xl space-y-6">
      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-white">Export</h1>
        <p className="text-sm text-white/40 mt-0.5">
          Export your rough cut to Adobe Premiere Pro, DaVinci Resolve, or any NLE
        </p>
      </motion.div>

      {/* ── Timeline summary ── */}
      {(timeline || entries.length > 0) ? (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel overflow-hidden"
        >
          <div className="h-0.5 bg-gradient-to-r from-accent via-accent/50 to-transparent" />
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Scissors size={13} className="text-accent" />
              <p className="text-xs font-semibold text-white/60 uppercase tracking-wider">Timeline Summary</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Name',     value: timeline?.name ?? 'Rough Cut' },
                { label: 'Clips',    value: timeline?.clip_count ?? entries.length },
                { label: 'Duration', value: formatDuration(timeline?.total_duration ?? totalDuration) },
                { label: 'Approved', value: approvedCount },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-2xs text-white/30 uppercase tracking-wider mb-0.5">{label}</p>
                  <p className="text-lg font-bold text-white">{value}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="panel p-8 text-center border-dashed border-white/10"
        >
          <Scissors size={24} className="text-white/15 mx-auto mb-3" />
          <p className="text-white/50 text-sm font-medium">No timeline found</p>
          <p className="text-xs text-white/30 mt-1">Generate a timeline from the Timeline Editor first</p>
        </motion.div>
      )}

      {/* ── Export task status ── */}
      <AnimatePresence>
        {exportTaskId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="panel p-4 flex items-center gap-3"
          >
            {isExporting ? (
              <Loader2 size={15} className="animate-spin text-accent flex-shrink-0" />
            ) : taskStatus?.status === 'SUCCESS' ? (
              <CheckCircle2 size={15} className="text-success flex-shrink-0" />
            ) : (
              <Clock size={15} className="text-white/40 flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <span className="text-xs text-white/70">
                Export: <span className="text-white font-medium">{taskStatus?.status ?? 'Queued'}</span>
                {taskStatus?.progress?.step && (
                  <span className="text-white/40 ml-1">— {taskStatus.progress.step}</span>
                )}
              </span>
              {isExporting && (
                <div className="mt-1.5 w-full h-1 bg-editor-active rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-accent rounded-full"
                    animate={{ width: ['0%', '70%', '90%'] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Export format cards ── */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-white/40 uppercase tracking-widest">Export Formats</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {EXPORT_FORMATS.map((fmt) => (
            <ExportCard
              key={fmt.id}
              {...fmt}
              onExport={fmt.onExport || (() => handleExport(fmt.formats))}
              onDownload={
                fmt.onDownload 
                  ? fmt.onDownload 
                  : () => {
                      if (timeline?.id && fmt.fmt) {
                        if (fmt.fmt === 'json') {
                          window.open(`/api/v1/timelines/${timeline.id}`, '_blank')
                        } else {
                          window.location.href = `/api/v1/timelines/${timeline.id}/download/${fmt.fmt}`
                        }
                      }
                    }
              }
              exporting={fmt.exporting || exportTimeline.isPending}
            />
          ))}
        </div>
      </div>

      {/* ── Export all ── */}
      {timeline && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-3"
        >
          <Button
            id="export-all-btn"
            variant="primary"
            size="lg"
            onClick={() => handleExport(['xml', 'edl', 'otio'])}
            loading={exportTimeline.isPending}
          >
            <Download size={14} /> Export All Formats
          </Button>
        </motion.div>
      )}

      {/* ── Premiere import instructions ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="panel p-4"
      >
        <p className="text-xs font-semibold text-white/60 mb-3">
          📽️ Premiere Pro Import Instructions
        </p>
        <ol className="space-y-1.5">
          {[
            'Download the XML file using the button above',
            'In Premiere Pro: File → Import → select the downloaded .xml file',
            'The sequence appears in your Project panel with all clips in order',
            'Relink media if prompted — point to your original 4K source files',
            'Review and fine-tune in Premiere as usual',
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-2.5 text-xs text-white/40">
              <span className="text-accent/60 font-mono font-bold flex-shrink-0 mt-0.5">{i + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
      </motion.div>
    </div>
  )
}
