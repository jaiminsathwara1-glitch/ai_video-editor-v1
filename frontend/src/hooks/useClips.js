import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clipsApi } from '@/api/clips'
import toast from 'react-hot-toast'

export const useClips = (projectId, params) =>
  useQuery({
    queryKey: ['clips', projectId, params],
    queryFn: () => clipsApi.list(projectId, params),
    enabled: !!projectId,
  })

export const useClip = (clipId) =>
  useQuery({
    queryKey: ['clip', clipId],
    queryFn: () => clipsApi.get(clipId),
    enabled: !!clipId,
  })

export const useDeleteClip = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: clipsApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['clips'] })
      toast.success('Clip removed')
    },
  })
}
