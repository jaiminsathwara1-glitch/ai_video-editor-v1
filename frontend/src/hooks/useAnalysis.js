import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { analysisApi } from '@/api/analysis'
import toast from 'react-hot-toast'

export const useClipAnalysis = (clipId) =>
  useQuery({
    queryKey: ['analysis', clipId],
    queryFn: () => analysisApi.getClip(clipId),
    enabled: !!clipId,
  })

export const useProjectScores = (projectId) =>
  useQuery({
    queryKey: ['scores', projectId],
    queryFn: () => analysisApi.projectScores(projectId),
    enabled: !!projectId,
  })

export const useTaskStatus = (taskId, { enabled = true, refetchInterval } = {}) =>
  useQuery({
    queryKey: ['task', taskId],
    queryFn: () => analysisApi.taskStatus(taskId),
    enabled: !!taskId && enabled,
    refetchInterval: (data) => {
      if (!data) return refetchInterval ?? 3000
      if (['SUCCESS', 'FAILURE'].includes(data.status)) return false
      return refetchInterval ?? 3000
    },
  })

export const useStartProjectAnalysis = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, analysisMode = 'gemini' }) => analysisApi.startProject(projectId, analysisMode),
    onSuccess: (data) => {
      toast.success(`Analysis started for ${data.dispatched ?? 0} clips`)
      qc.invalidateQueries({ queryKey: ['clips'] })
    },
  })
}

export const useDetectDuplicates = () =>
  useMutation({ mutationFn: analysisApi.detectDupes,
    onSuccess: () => toast.success('Duplicate detection queued') })
