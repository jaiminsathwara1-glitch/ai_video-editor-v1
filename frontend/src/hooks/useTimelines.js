import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { timelinesApi } from '@/api/timelines'
import { useTimelineStore } from '@/stores/timelineStore'
import toast from 'react-hot-toast'

export const useTimelines = (projectId) =>
  useQuery({
    queryKey: ['timelines', projectId],
    queryFn: () => timelinesApi.list(projectId),
    enabled: !!projectId,
    refetchInterval: 3000,
  })

export const useTimeline = (id) =>
  useQuery({
    queryKey: ['timeline', id],
    queryFn: () => timelinesApi.get(id),
    enabled: !!id,
  })

export const useGenerateTimeline = () => {
  const qc = useQueryClient()
  const setTimeline = useTimelineStore((s) => s.setTimeline)
  return useMutation({
    mutationFn: timelinesApi.generate,
    onSuccess: (timeline) => {
      setTimeline(timeline)
      qc.invalidateQueries({ queryKey: ['timelines'] })
      toast.success(`Timeline generated — ${timeline.clip_count} clips`)
    },
  })
}

export const useReorderTimeline = () => {
  const setTimeline = useTimelineStore((s) => s.setTimeline)
  return useMutation({
    mutationFn: ({ timelineId, analysisMode }) => timelinesApi.reorder(timelineId, analysisMode),
    onSuccess: (timeline) => {
      setTimeline(timeline)
      toast.success('Clips reordered by AI ✨')
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err.message || 'Reorder failed'
      toast.error(`AI Reorder failed: ${msg}`)
    },
  })
}

export const useExportTimeline = () => {
  return useMutation({
    mutationFn: ({ id, formats }) => {
      if (formats?.length === 1 && formats[0] === 'xml') return timelinesApi.exportXml(id)
      if (formats?.length === 1 && formats[0] === 'edl') return timelinesApi.exportEdl(id)
      return timelinesApi.exportAll(id)
    },
    onSuccess: () => toast.success('Export queued — check back in a moment'),
  })
}

export const useDownloadTimeline = () => {
  return useMutation({
    mutationFn: async ({ id, fmt }) => {
      const blob = await timelinesApi.download(id, fmt)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `timeline_${id.slice(0, 8)}.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
    },
    onSuccess: () => toast.success('Download started'),
  })
}

export const useRenderTimelineVideo = () => {
  return useMutation({
    mutationFn: ({ id }) => timelinesApi.renderVideo(id),
    onSuccess: () => toast.success('Video rendering queued — check back in a moment'),
  })
}

export const useDownloadTimelineVideo = () => {
  return useMutation({
    mutationFn: async ({ id }) => {
      const blob = await timelinesApi.downloadVideo(id)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `roughcut_${id.slice(0, 8)}.mp4`
      a.click()
      URL.revokeObjectURL(url)
    },
    onSuccess: () => toast.success('Download started'),
  })
}
