import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/api/projects'
import { useProjectStore } from '@/stores/projectStore'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

export const useProjects = () =>
  useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

export const useProject = (id) =>
  useQuery({
    queryKey: ['project', id],
    queryFn: () => projectsApi.get(id),
    enabled: !!id,
  })

export const useProjectStats = (id) =>
  useQuery({
    queryKey: ['project-stats', id],
    queryFn: () => projectsApi.stats(id),
    enabled: !!id,
    refetchInterval: 5000,
  })

export const useCreateProject = () => {
  const qc = useQueryClient()
  const { setCurrentProject, addRecent } = useProjectStore()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setCurrentProject(project.id)
      addRecent({ id: project.id, name: project.name, createdAt: project.created_at })
      toast.success(`Project "${project.name}" created`)
      navigate(`/upload?project=${project.id}`)
    },
  })
}

export const useDeleteProject = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: projectsApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      toast.success('Project deleted')
    },
  })
}
